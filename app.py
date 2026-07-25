import math
import traceback
from flask import Flask, render_template, request, jsonify
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor
)

app = Flask(__name__)

# Symbol for series index
n = sp.Symbol('n', integer=True, positive=True)

def safe_parse(expr_str):
    """
    Safely parses mathematical expression strings into SymPy expressions.
    Supports caret '^' for exponentiation and implicit multiplication like '2n'.
    """
    expr_str = expr_str.strip()
    if not expr_str:
        raise ValueError("El término general a_n no puede estar vacío.")

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor
    )
    
    # Custom local dictionary for common mathematical functions
    local_dict = {
        'n': n,
        'e': sp.E,
        'pi': sp.pi,
        'sin': sp.sin,
        'cos': sp.cos,
        'tan': sp.tan,
        'ln': sp.log,
        'log': sp.log,
        'exp': sp.exp,
        'sqrt': sp.sqrt,
        'factorial': sp.factorial,
        'oo': sp.oo,
        'inf': sp.oo
    }
    
    parsed = parse_expr(expr_str, local_dict=local_dict, transformations=transformations)
    return parsed

def compute_partial_sums(a_n_expr, start_n=1, num_terms=20):
    """
    Calculates partial sums S_N = sum_{n=start_n}^N a_n for plotting.
    """
    data = []
    current_sum = 0.0
    
    for i in range(start_n, start_n + num_terms):
        try:
            val_sym = a_n_expr.subs(n, i)
            val_num = float(val_sym.evalf())
            if math.isnan(val_num) or math.isinf(val_num):
                break
            current_sum += val_num
            data.append({
                'n': i,
                'an': round(val_num, 6),
                'Sn': round(current_sum, 6)
            })
        except Exception:
            break
            
    return data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        req_data = request.get_json() or {}
        raw_expr = req_data.get('expression', '1/n**2')
        start_n = int(req_data.get('start_n', 1))
        num_terms = int(req_data.get('num_terms', 20))

        if start_n < 0:
            return jsonify({'success': False, 'error': 'El índice inicial n debe ser >= 0.'}), 400

        # Parse SymPy expression
        a_n = safe_parse(raw_expr)

        # LaTeX representation of general term and series
        a_n_latex = sp.latex(a_n)
        series_latex = f"\\sum_{{n={start_n}}}^\\infty {a_n_latex}"

        # 1. Divergence Test: limit as n -> oo of a_n
        try:
            limit_an = sp.limit(a_n, n, sp.oo)
        except Exception:
            try:
                abs_lim = sp.limit(sp.Abs(a_n), n, sp.oo)
                if abs_lim == 0:
                    limit_an = sp.Integer(0)
                else:
                    limit_an = abs_lim
            except Exception:
                limit_an = sp.Symbol('Indefinido')

        limit_an_latex = sp.latex(limit_an)

        tests_results = []
        status = "INDETERMINADO"
        sum_exact_latex = None
        sum_numeric = None

        # Test 1: Divergence Test (Término General)
        if limit_an != 0:
            status = "DIVERGENTE"
            div_test_conclusion = "Diverge"
            div_test_detail = f"Dado que \\lim_{{n \\to \\infty}} a_n = {limit_an_latex} \\neq 0, la serie DIVERGE por el Criterio del Término General."
        else:
            div_test_conclusion = "Inconcluso"
            div_test_detail = f"Dado que \\lim_{{n \\to \\infty}} a_n = 0, este criterio es inconcluso (la serie puede converger o diverger)."

        tests_results.append({
            'name': 'Criterio del Término General (Divergencia)',
            'formula': f"\\lim_{{n \\to \\infty}} a_n = {limit_an_latex}",
            'conclusion': div_test_conclusion,
            'details': div_test_detail
        })

        # Test 1.5: Leibniz Test for Alternating Series
        if a_n.has(sp.Pow(-1, n)) or a_n.has(sp.Pow(-1, n + 1)) or a_n.has(sp.Pow(-1, n - 1)):
            try:
                b_n = sp.Abs(a_n)
                lim_bn = sp.limit(b_n, n, sp.oo)
                if lim_bn == 0:
                    leibniz_conclusion = "Converge (Leibniz)"
                    leibniz_detail = f"Es una serie alternada con \\lim_{{n \\to \\infty}} |a_n| = 0 \\implies \\text{{CONVERGE por Criterio de Leibniz.}}"
                    if status == "INDETERMINADO":
                        status = "CONVERGENTE"
                else:
                    leibniz_conclusion = "Diverge"
                    leibniz_detail = f"Serie alternada cuyo límite de magnitud \\lim |a_n| = {sp.latex(lim_bn)} \\neq 0 \\implies \\text{{DIVERGE.}}"
                    status = "DIVERGENTE"
                tests_results.append({
                    'name': 'Criterio de Leibniz (Series Alternadas)',
                    'formula': f"a_n = (-1)^n b_n, \\quad \\lim_{{n \\to \\infty}} b_n = {sp.latex(lim_bn)}",
                    'conclusion': leibniz_conclusion,
                    'details': leibniz_detail
                })
            except Exception:
                pass

        # Test 1.75: p-Series Test (Criterio de la Serie p)
        # Detects if a_n = C / n^p  (i.e. a_n = C * n^(-p)) and applies the p-series rule
        try:
            # Simplify expression and check if it's of the form C * n^(-p)
            simplified = sp.simplify(a_n)
            # Extract the exponent of n: if a_n = C*n^alpha, then alpha should be negative
            # Use leading term analysis
            coeff_wild = sp.Wild('C', exclude=[n])
            exp_wild = sp.Wild('p')
            
            is_p_series = False
            p_val = None
            C_val = None
            
            # Try matching a_n = C * n^(-p) directly
            match = simplified.match(coeff_wild * n**exp_wild)
            if match and coeff_wild in match and exp_wild in match:
                C_val = match[coeff_wild]
                exponent = match[exp_wild]
                # Check C doesn't depend on n and exponent is a constant
                if not C_val.has(n) and not exponent.has(n):
                    p_val = -exponent  # a_n = C*n^(-p), so p = -exponent
                    is_p_series = True
            
            # Also try matching a_n = 1/n^p  ->  n^(-p)
            if not is_p_series:
                match2 = simplified.match(n**exp_wild)
                if match2 and exp_wild in match2:
                    exponent = match2[exp_wild]
                    if not exponent.has(n):
                        p_val = -exponent
                        C_val = sp.Integer(1)
                        is_p_series = True
            
            if is_p_series and p_val is not None:
                p_val_latex = sp.latex(p_val)
                if p_val > 1:
                    p_conclusion = "Converge"
                    p_detail = f"a_n = \\frac{{{sp.latex(C_val)}}}{{n^{{{p_val_latex}}}}} \\text{{ es una serie p con }} p = {p_val_latex} > 1 \\implies \\text{{CONVERGE.}}"
                    if status == "INDETERMINADO":
                        status = "CONVERGENTE"
                elif p_val <= 1:
                    p_conclusion = "Diverge"
                    p_detail = f"a_n = \\frac{{{sp.latex(C_val)}}}{{n^{{{p_val_latex}}}}} \\text{{ es una serie p con }} p = {p_val_latex} \\leq 1 \\implies \\text{{DIVERGE.}}"
                    if status == "INDETERMINADO":
                        status = "DIVERGENTE"
                else:
                    p_conclusion = "Inconcluso"
                    p_detail = f"\\text{{No se pudo determinar el valor de p.}}"

                tests_results.append({
                    'name': 'Criterio de la Serie p',
                    'formula': f"a_n = \\frac{{{sp.latex(C_val)}}}{{n^{{{p_val_latex}}}}}, \\quad p = {p_val_latex}",
                    'conclusion': p_conclusion,
                    'details': p_detail
                })
        except Exception:
            pass

        # Test 2: Ratio Test (Criterio de D'Alembert / de la Razón)
        try:
            a_n_plus_1 = a_n.subs(n, n + 1)
            ratio_expr = sp.Abs(a_n_plus_1 / a_n)
            ratio_limit = sp.limit(ratio_expr, n, sp.oo)
            ratio_limit_latex = sp.latex(ratio_limit)

            if ratio_limit < 1:
                ratio_conclusion = "Converge Absolutamente"
                ratio_detail = f"L = {ratio_limit_latex} < 1 \\implies \\text{{La serie CONVERGE absolutamente.}}"
                if status == "INDETERMINADO":
                    status = "CONVERGENTE"
            elif ratio_limit > 1:
                ratio_conclusion = "Diverge"
                ratio_detail = f"L = {ratio_limit_latex} > 1 \\implies \\text{{La serie DIVERGE.}}"
                if status == "INDETERMINADO":
                    status = "DIVERGENTE"
            else:
                ratio_conclusion = "Inconcluso"
                ratio_detail = f"L = {ratio_limit_latex} = 1 \\implies \\text{{Criterio inconcluso.}}"

            tests_results.append({
                'name': "Criterio de D'Alembert (de la Razón)",
                'formula': f"L = \\lim_{{n \\to \\infty}} \\left| \\frac{{a_{{n+1}}}}{{a_n}} \\right| = {ratio_limit_latex}",
                'conclusion': ratio_conclusion,
                'details': ratio_detail
            })
        except Exception:
            pass

        # Test 3: Root Test (Criterio de Cauchy / de la Raíz)
        try:
            root_expr = sp.Abs(a_n)**(1/n)
            root_limit = sp.limit(root_expr, n, sp.oo)
            root_limit_latex = sp.latex(root_limit)

            if root_limit < 1:
                root_conclusion = "Converge Absolutamente"
                root_detail = f"L = {root_limit_latex} < 1 \\implies \\text{{La serie CONVERGE absolutamente.}}"
                if status == "INDETERMINADO":
                    status = "CONVERGENTE"
            elif root_limit > 1:
                root_conclusion = "Diverge"
                root_detail = f"L = {root_limit_latex} > 1 \\implies \\text{{La serie DIVERGE.}}"
                if status == "INDETERMINADO":
                    status = "DIVERGENTE"
            else:
                root_conclusion = "Inconcluso"
                root_detail = f"L = {root_limit_latex} = 1 \\implies \\text{{Criterio inconcluso.}}"

            tests_results.append({
                'name': "Criterio de Cauchy (de la Raíz)",
                'formula': f"L = \\lim_{{n \\to \\infty}} \\sqrt[n]{{|a_n|}} = {root_limit_latex}",
                'conclusion': root_conclusion,
                'details': root_detail
            })
        except Exception:
            pass

        # 2. Infinite Summation via SymPy
        try:
            total_sum = sp.summation(a_n, (n, start_n, sp.oo))
            if total_sum.has(sp.Sum):
                # SymPy couldn't evaluate closed form directly
                sum_exact_latex = "\\text{No evaluable en forma cerrada}"
            elif total_sum is sp.oo or total_sum is -sp.oo or total_sum is sp.zoo:
                status = "DIVERGENTE"
                sum_exact_latex = sp.latex(total_sum)
            else:
                status = "CONVERGENTE"
                sum_exact_latex = sp.latex(total_sum)
                try:
                    sum_numeric = float(total_sum.evalf())
                    if math.isnan(sum_numeric) or math.isinf(sum_numeric):
                        sum_numeric = None
                except Exception:
                    sum_numeric = None
        except Exception as e:
            sum_exact_latex = "\\text{No evaluable}"

        # 3. Exact N-th Partial Sum S_N for Condition b
        end_n = start_n + num_terms - 1
        sn_exact_latex = None
        sn_numeric = None
        try:
            sn_sym = sp.summation(a_n, (n, start_n, end_n))
            sn_exact_latex = f"S_{{{num_terms}}} = " + sp.latex(sn_sym)
            try:
                sn_numeric = float(sn_sym.evalf())
            except Exception:
                sn_numeric = None
        except Exception:
            sn_exact_latex = None

        # 4. Partial sums sequence (for plotting & table)
        partial_sums = compute_partial_sums(a_n, start_n, num_terms)

        return jsonify({
            'success': True,
            'expression_latex': a_n_latex,
            'series_latex': series_latex,
            'status': status,
            'limit_an_latex': limit_an_latex,
            'sum_exact_latex': sum_exact_latex,
            'sum_numeric': sum_numeric,
            'num_terms_N': num_terms,
            'sn_exact_latex': sn_exact_latex,
            'sn_numeric': sn_numeric,
            'tests': tests_results,
            'partial_sums': partial_sums
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
