import argparse
import html.parser as parser
import os
import re
import time
from enum import Enum, auto


class env(Enum):
    document = auto()
    figure = auto()
    itemize = auto()
    enumerate = auto()
    table = auto()
    raw = auto()
    equation = auto()

INFO = '\033[0;37;42mInfo\033[0m '
WARN = '\033[0;37;43mWarning\033[0m '
ERROR = '\033[0;37;41mError\033[0m '

class MdHtmlParser(parser.HTMLParser):
    """Tiny HTML start tag collector (only first tag is kept)."""
    def __init__(self):
        super().__init__()
        self.tag = None
        self.attrs = None
    def handle_starttag(self, tag, attrs):
        if self.tag is None:  # only record the first for efficiency
            self.tag = tag
            self.attrs = dict(attrs)

KNOWN_INLINE_HTML_TAGS = {
    'img', 'a', 'br', 'hr', 'span', 'strong', 'em', 'code', 'u', 'font'
}

MATH_INLINE_PATTERN = re.compile(r'\$(?:[^$\\]|\\.)+\$')  # $...$ with simple escaping

def _mask_segments(pattern, text, placeholder_prefix):
    """Mask segments matched by pattern to protect them from downstream regex replacements.
    Returns masked_text, list of (placeholder, original_text)."""
    replacements = []
    def repl(match):
        placeholder = f'__{placeholder_prefix}{len(replacements)}__'
        replacements.append((placeholder, match.group(0)))
        return placeholder
    masked = pattern.sub(repl, text)
    return masked, replacements

def _unmask(text, replacements):
    for placeholder, original in replacements:
        text = text.replace(placeholder, original)
    return text

def mask_math_and_code(line):
    """Mask inline math $...$ and code `...` blocks to avoid accidental formatting or HTML detection."""
    masked, math_repls = _mask_segments(MATH_INLINE_PATTERN, line, 'MATH')
    code_pattern = re.compile(r'`[^`]+`')
    masked, code_repls = _mask_segments(code_pattern, masked, 'CODE')
    return masked, math_repls + code_repls

def has_html(line):
    """More conservative HTML detection that ignores content inside math/code placeholders.
    We only consider as HTML if a known tag begins with <tag ...> or <tag>.
    Angle brackets in math like $a<b$ or vector notation <x,y> will NOT be treated as HTML.
    """
    if '<' not in line or '>' not in line:
        return False
    # Quick reject: ignore placeholders
    tmp = line
    # Recognize minimal pattern: <tag ...>
    candidate_tags = re.findall(r'<\s*([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', tmp)
    for t in candidate_tags:
        if t.lower() in KNOWN_INLINE_HTML_TAGS:
            return True
    return False

def arg_parser():
    parser = argparse.ArgumentParser(description='Convert markdown to latex')
    parser.add_argument('--md-file', type=str, default='report.md', help='The markdown file to be converted')
    parser.add_argument('--tex-file', type=str, help='The output tex file')
    parser.add_argument('--template', type=str, help='The template tex file')
    parser.add_argument('--figure-pos', type=str, default='ht', help='The position of the figure')
    parser.add_argument('--table-pos', type=str, default='ht', help='The position of the table')
    parser.add_argument('-o', action='store_true', help='Overwrite the existing tex file')
    parser.add_argument('-v', action='store_true', help='Use VLOOK style cross-reference, else pandoc style')
    parser.add_argument("--spaces", type=int, default=4, help="Number of spaces for each indentation level")
    parser.add_argument("--code-type", type=str, default="minted", help="How to handle code text")
    parser.add_argument(
        "-have-title",
        action="store_true",
        help=("Whether the document has a title; if True, '#' remains plain and '##' becomes \\section; "
              "otherwise '#' becomes \\section."),
    )
    return parser.parse_args()

# 将markdown中的表格转换为latex格式
def tables_convert(tables, with_caption, args):
    def replace_func(match):
        s = match.group(0).strip()
        if s.isspace():
            return r'\textbf{}'
        else:
            return r'\textbf{' + s + '}'

    ret_tables = []
    indent = ' ' * args.spaces  # 获取动态缩进
    for table in tables:
        label, caption = None, None
        table = table[0].split('\n')
        if with_caption:
            label_caption = table[0]
            for i in range(1, len(table) - 1):
                if table[i] == '':
                    i +=1
                else:
                    break
            header = table[i]
            alignment = table[i + 1]
            body = table[i + 2:]
        else:
            header = table[0]
            alignment = table[1]
            body = table[2:]

        if with_caption:
            label_caption = re.findall(r'\*==(.*?)==\*', label_caption)[0]
            # 如果有下划线，则分别为label和caption，否则只有caption
            if '_' in label_caption:
                label, caption = label_caption.split('_')
            else:
                label = None
                caption = label_caption
        
        if caption:
            ret_table = (
                f"\\begin{{table}}[" + args.table_pos + f"]\n"
                f"{indent}\\centering\n"
                f"{indent}\\caption{{{caption}}}\n"
                f"{indent}\\begin{{tabular}}" + '{'
            )
        else:
            ret_table = (
                f"\\begin{{table}}[" + args.table_pos + f"]\n"
                f"{indent}\\centering\n"
                f"{indent}\\begin{{tabular}}" + '{'
            )
        aligns = re.findall(r':?-+:?|:-+|-+:', alignment)
        for align in aligns:
            if align.startswith(':') and align.endswith(':'):
                ret_table += 'c'
            elif align.endswith(':'):
                ret_table += 'r'
            else:
                ret_table += 'l'
        ret_table += f'}}\n{indent}{indent}\\toprule\n'
        # change the header to bold
        ret_header = re.sub(r'^\||\|$', '', re.sub(r'\|', ' & ', header))
        ret_header = re.sub(r'^\s*&|&\s*$', '', re.sub(r'\|', ' & ', header))
        ret_header = re.sub(r'[^&]+', replace_func, ret_header)
        ret_table += '        ' + ret_header + ' \\\\\n        \\midrule\n'
        for i in range(len(body) - 1):
            ret_body = re.sub(r'^\||\|$', '', re.sub(r'\|', ' & ', body[i]))
            ret_body = re.sub(r'^\s*&|&\s*$', '', re.sub(r'\|', ' & ', body[i]))
            # ret_body = re.sub(r'[^&]+', replace_func, ret_body)
            ret_table += f'{indent}{indent}' + ret_body + ' \\\\\n'
        if label:
            ret_table += (
                f"{indent}{indent}\\bottomrule\n"
                f"{indent}\\end{{tabular}}\n"
                f"{indent}\\label{{{label}}}\n"
                f"\\end{{table}}\n"
            )
        else:
            ret_table += (
                f"{indent}{indent}\\bottomrule\n"
                f"{indent}\\end{{tabular}}\n"
                f"\\end{{table}}\n"
            )
        ret_tables.append(ret_table)
    return ret_tables

def equations_convert(equations, with_caption, args):
    ret_eqs = []
    indent = ' ' * args.spaces  # 获取动态缩进
    for eq in equations:
        label = None
        if with_caption:
            label = eq[1]
            eq = eq[2]
        else:
            eq = eq[1]
        if re.match(r'^\s*\\begin{align}', eq):
            eq = re.sub(r'^\s*\\begin{align}', r'\\begin{align*}', eq)
            eq = re.sub(r'\\end{align}', r'\\end{align*}', eq)
        # 删除eq最前面和最后面的换行符
        eq = re.sub(r'^\n+|\n+$', '', eq)
        if label:
            ret_eq = f'{eq}\n\\label{{{label}}}'
        else:
            ret_eq = f'{eq}'
        # 每行前面加上四个空格
        ret_eq = re.sub(r'^', f'{indent}', ret_eq, flags=re.MULTILINE)
        ret_eq = "\\begin{equation}\n" + ret_eq + "\n\\end{equation}"
        ret_eqs.append(ret_eq)
    return ret_eqs

def md_to_tex(md_content, args):
    indent = ' ' * args.spaces  # 获取动态缩进
    have_title = args.have_title

    # 提取带标题的表格内容
    table_label_pattern = re.compile(r"(\*==(.+?)==\*\n+\|.*?\|\n(\|.*?\|\n)+(\|.*?\|\n)*)", re.DOTALL)
    tables = table_label_pattern.findall(md_content)
    if tables:
        tex_tables = tables_convert(tables, True, args)
        for i in range(len(tables)):
            md_content = md_content.replace(tables[i][0], tex_tables[i])
    
    # 提取不带标题的表格内容
    table_pattern = re.compile(r"(\|.*?\|\n(\|.*?\|\n)+(\|.*?\|\n)*)", re.DOTALL)
    tables = table_pattern.findall(md_content)
    if tables:
        tex_tables = tables_convert(tables, False, args)
        for i in range(len(tables)):
            md_content = md_content.replace(tables[i][0], tex_tables[i])
    
    # 提取带标题的公式内容
    equation_label_pattern = re.compile(r"(\*==(.+?)==\*\n+\$\$(.+?)\$\$)", re.DOTALL)
    equations = equation_label_pattern.findall(md_content)
    if equations:
        tex_equations = equations_convert(equations, True, args)
        for i in range(len(equations)):
            md_content = md_content.replace(equations[i][0], tex_equations[i])
        
    # 提取不带标题的公式内容
    equation_pattern = re.compile(r"(\$\$(.+?)\$\$)", re.DOTALL)
    equations = equation_pattern.findall(md_content)
    if equations:
        tex_equations = equations_convert(equations, False, args)
        for i in range(len(equations)):
            md_content = md_content.replace(equations[i][0], tex_equations[i])
    
    # 检测是否有一级标题存在
    if re.match(r'^#\s', md_content):
        level1 = True
    else:
        level1 = False
    
    if have_title:
        level1 = False
    
    if level1 == False:
        # 删除所有一级标题，将#以及后续文字及换行符删除
        md_content = re.sub(r'^#\s.*\n*', '', md_content)

    # 将md_content按行分割
    md_content = md_content.split('\n')
    tex_content = ''
    env_stack = []
    env_stack.append(env.document)
    align_flag = False

    md_index = -1
    for md_line in md_content:
        tex_line = md_line
        md_index += 1

        # 处理空行
        if md_line == '': 
            tex_content += '\n'
            continue

        # 处理代码块
        if re.match(r'^\s*```', tex_line):
            # 获取当前代码块的语言
            if env_stack[-1] != env.raw:
                lang = re.match(r'^\s*```(\w+)', tex_line).group(1)
                if args.code_type == 'lstlisting':
                    tex_content += f'\\begin{{lstlisting}}[language={lang}]\n'
                else:
                    tex_content += f'\\begin{{minted}}{{{lang}}}\n'
                env_stack.append(env.raw)
            else:
                if args.code_type == 'lstlisting':
                    tex_content += '\\end{lstlisting}\n'
                else:
                    tex_content += '\\end{minted}\n'
                env_stack.pop()
            continue

        # 处理公式块
        # if re.match(r'^\$\$', tex_line):
        #     if env_stack[-1] != env.equation:
        #         env_stack.append(env.equation)
        #         # if next line is \begin{align}, then use align environment
        #         if re.match(r'^\s*\\begin{align}', md_content[md_index + 1]):
        #             align_flag = True
        #         else:
        #             tex_content += '\\begin{equation}\n'
        #     else: 
        #         env_stack.pop()
        #         if align_flag:
        #             align_flag = False
        #         else:
        #             tex_content += '\\end{equation}\n'
        #     continue

        # if re.match(r'^\s*\\begin{table}', tex_line):
        #     env_stack.append(env.table)
        # if re.match(r'^\s*\\end{table}', tex_line):
        #     env_stack.pop()

        # Detect entering / leaving standard math environments produced earlier
        if re.match(r'^\\begin{(equation|align\*?|gather\*?)}', tex_line):
            env_stack.append(env.equation)
        if re.match(r'^\\end{(equation|align\*?|gather\*?)}', tex_line):
            if env_stack and env_stack[-1] == env.equation:
                env_stack.pop()

        # 如果当前处于代码块或公式块中（equation env），直接写入
        if env_stack[-1] in [env.equation, env.raw]:
            tex_content += tex_line + '\n'
            continue

        # --- Inline formatting (protect math & code first) ---
        masked_line, repls = mask_math_and_code(tex_line)

        # *==label==* -> \label{label}
        masked_line = re.sub(r'\*==(.*?)==\*', r'\\label{\1}', masked_line)

        # **text** -> \textbf{text}
        masked_line = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', masked_line)

        # *text* -> \textit{text} (avoid conflicts with already converted **)
        masked_line = re.sub(r'(?<!\\)\*(?!\*)([^*]+?)\*(?!\*)', r'\\textit{\1}', masked_line)

        # inline code placeholders are restored later; convert actual inline code to minted/verb
        # (Already masked, so we transform after unmask)

        tex_line = _unmask(masked_line, repls)

        # Support underline <u>...</u>
        def _u_repl(m):
            inner = m.group(1).strip()
            return f'\\underline{{{inner}}}'
        tex_line = re.sub(r'<u[^>]*>(.+?)</u>', _u_repl, tex_line, flags=re.IGNORECASE)

        # Support <font color=...>...</font> (simplified); require \usepackage{xcolor} in template
        def _font_repl(m):
            color = m.group(1)
            inner = m.group(2).strip()
            return f'\\textcolor{{{color}}}{{{inner}}}'
        tex_line = re.sub(r'<font[^>]*?color\s*=\s*["\']?([A-Za-z]+)["\']?[^>]*>(.+?)</font>', _font_repl, tex_line, flags=re.IGNORECASE)

        # `code` -> inline code formatting (now safe because math restored)
        if args.code_type == 'lstlisting':
            tex_line = re.sub(r'`([^`]+?)`', r'\\verb|\1|', tex_line)
        else:
            tex_line = re.sub(r'`([^`]+?)`', r'\\mintinline{text}|\1|', tex_line)

        # 根据是否有一级标题进行处理
        if level1:
            # # section -> \section{section}
            tex_line = re.sub(r'^#\s+(.*)', r'\\section{\1}', tex_line)
            
            # ## subsection -> \subsection{subsection}
            tex_line = re.sub(r'^##\s+(.*)', r'\\subsection{\1}', tex_line)
            
            # ### subsubsection -> \subsubsection{subsubsection}
            tex_line = re.sub(r'^###\s+(.*)', r'\\subsubsection{\1}', tex_line)

        else:
            # ## section -> \section{section}
            tex_line = re.sub(r'^##\s+(.*)', r'\\section{\1}', tex_line)
            
            # ### subsection -> \subsection{subsection}
            tex_line = re.sub(r'^###\s+(.*)', r'\\subsection{\1}', tex_line)
            
            # #### subsubsection -> \subsubsection{subsubsection}
            tex_line = re.sub(r'^####\s+(.*)', r'\\subsubsection{\1}', tex_line)
        
        # ###### paragraph -> \paragraph{paragraph}
        tex_line = re.sub(r'^######\s+(.*)', r'\\paragraph{\1}', tex_line)


        # # _ -> \_ if _ is not preceded by \ and not in inline math mode
        # tex_line = re.sub(r'(?<!\\)(?<!\\$)_', r'\\_', tex_line)

        # # % -> \%
        if not has_html(tex_line):
            tex_line = re.sub(r'([^\\])%', r'\1\\%', tex_line)

        # [@reference] -> \cite{reference}
        tex_line = re.sub(r'\[@(.*?)\]', r'\\cite{\1}', tex_line)

        # [#label] -> \ref{label}
        tex_line = re.sub(r'\[#(.*?)\]', r'\\ref{\1}', tex_line)
        
        # 处理图片，顺序不要颠倒
        # ![](img_path "caption") -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n    \caption{caption}\\n\end{figure}
        tex_line = re.sub(
            r'!\[\]\((.*?)\s*"(.*?)"\)',
            r'\\begin{figure}[' + args.figure_pos + r']\n' + indent + r'\\centering\n' + indent + r'\\includegraphics[width=\\textwidth]{\1}\n' + indent + r'\\caption{\2}\n' + r'\\end{figure}',
            tex_line
        )
        # ![](img_path) -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n\end{figure}
        tex_line = re.sub(
            r'!\[\]\((.*?)\)',
            r'\\begin{figure}[' + args.figure_pos + r']\n' + indent + r'\\centering\n' + indent + r'\\includegraphics[width=\\textwidth]{\1}\n' + r'\\end{figure}',
            tex_line
        )
        # ![label](img_path "caption") -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n    \caption{caption}\n    \label{label}\n\end{figure}
        tex_line = re.sub(
            r'!\[(.*?)\]\((.*?)\s*"(.*?)"\)',
            r'\\begin{figure}[' + args.figure_pos + r']\n' + indent + r'\\centering\n' + indent + r'\\includegraphics[width=\\textwidth]{\2}\n' + indent + r'\\caption{\3}\n' + indent + r'\\label{\1}\n' + r'\\end{figure}',
            tex_line
        )
        # ![label](img_path) -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n    \label{label}\n\end{figure}
        tex_line = re.sub(
            r'!\[(.*?)\]\((.*?)\)',
            r'\\begin{figure}[' + args.figure_pos + r']\n' + indent + r'\\centering\n' + indent + r'\\includegraphics[width=\\textwidth]{\2}\n' + indent + r'\\label{\1}\n' + r'\\end{figure}',
            tex_line
        )

        # [label](url) -> \href{url}{label}
        tex_line = re.sub(r'\[(.*?)\]\((.*?)\)', r'\\href{\2}{\1}', tex_line)

        # HTML标签处理 (after other inline conversions to avoid impacting replacements)
        if has_html(tex_line):
            html_parser = MdHtmlParser()
            html_parser.feed(tex_line)
            tag = html_parser.tag
            attrs = html_parser.attrs or {}
            if tag == 'img':
                if 'src' not in attrs:
                    print(WARN + 'The img tag must have a src attribute, replaced with blank content')
                    tex_line = re.sub(r'<[^>]+>', '', tex_line)
                else:
                    # Build figure environment string (avoid raw string escape warnings)
                    html_line = ('\\begin{figure}[' + args.figure_pos + f']\n'
                                  f'{indent}\\centering\n'
                                  f'{indent}\\includegraphics[width=')
                    if 'style' in attrs:
                        zoom = re.search(r'zoom:\s*(\d+)%', attrs['style'])
                        if zoom:
                            html_line += f'{int(zoom.group(1)) / 100:.2f}\\textwidth'
                        else:
                            html_line += r'\textwidth'
                    else:
                        html_line += r'\textwidth'
                    html_line += f']{{{attrs["src"]}}}\n'
                    if 'title' in attrs:
                        html_line += f'{indent}\\caption{{{attrs["title"]}}}\n'
                    if 'alt' in attrs:
                        html_line += f'{indent}\\label{{{attrs["alt"]}}}\n'
                    html_line += '\\end{figure}'
                    tex_line = html_line
            else:
                print(WARN + f'Unsupported HTML tag: {tag}, stripped.')
                tex_line = re.sub(r'<[^>]+>', '', tex_line)


        # 处理无序列表
        if md_line.startswith('- '):
            if env_stack[-1] != env.itemize:
                tex_content += '\\begin{itemize}\n'
                env_stack.append(env.itemize)
            tex_line = re.sub(r'^\s*-\s+(.*)', indent + r'\\item \1', tex_line)
        else:
            if env_stack[-1] == env.itemize:
                # 删除tex_content最后一个换行符
                tex_content = tex_content[:-1]
                tex_content += '\\end{itemize}\n\n'
                env_stack.pop()

        # 处理有序列表
        if re.match(r'^\s*\d+\.\s+', md_line):
            if env_stack[-1] != env.enumerate:
                tex_content += '\\begin{enumerate}\n'
                env_stack.append(env.enumerate)
            tex_line = re.sub(r'^\s*\d+\.\s+(.*)', indent + r'\\item \1', tex_line)
        else:
            if env_stack[-1] == env.enumerate:
                # 删除tex_content最后一个换行符
                tex_content = tex_content[:-1]
                tex_content += '\\end{enumerate}\n\n'
                env_stack.pop()
        
        # 为每一段添加\par
        # if not tex_line.startswith('\\') and env_stack[-1] not in [env.itemize, env.enumerate, env.table]:
        #     tex_line = '\\par ' + tex_line

        tex_content += tex_line + '\n'
    
    # 关闭所有未关闭的环境
    while len(env_stack) > 1:
        if env_stack[-1] == env.itemize:
            tex_content += '\\end{itemize}\n'
        elif env_stack[-1] == env.enumerate:
            tex_content += '\\end{enumerate}\n'
        env_stack.pop()

    return tex_content

def main():
    args = arg_parser()
    with open(args.md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    tex_content = md_to_tex(md_content, args)
    if args.template is not None:
        with open(args.template, 'r', encoding='utf-8') as f:
            template_content = f.read()
        begin_marker = r'% ----- begin md -----'
        end_marker = r'% ----- end md -----'
        begin_index = template_content.find(begin_marker) + len(begin_marker)
        end_index = template_content.find(end_marker)
        template_begin = template_content[:begin_index]
        template_end = template_content[end_index:]
        tex_content = template_begin + '\n' + tex_content + template_end
    if args.tex_file is None:
        args.tex_file = args.md_file.replace('.md', '.tex')
    if os.path.exists(args.tex_file) and not args.o:
        print(f'File \"{args.tex_file}\" already exists, we add a suffix to the file name')
        args.tex_file = args.tex_file.replace('.tex', ' (1).tex')
        for i in range(1, 100000):
            if os.path.exists(args.tex_file):
                args.tex_file = args.tex_file.replace(f'({i}).tex', f'({i+1}).tex')
            else:
                break
        if i == 100000:
            print('\033[0;37;41m' + 'Error' + '\033[0m' + ' Too many files with the same name, please delete some files')
            exit(1)

    with open(args.tex_file, 'w', encoding='utf-8') as f:
        f.write(tex_content)
    print(f'Output file: \"{args.tex_file}\"')

if __name__ == '__main__':
    start_time = time.time()
    # try:
    main()
    end_time = time.time()
    print(INFO + f'Conversion completed in \033[94m{end_time - start_time:.2f}\033[0m seconds')
    # except Exception as e:
    #     print(ERROR + 'An error occurred during the conversion')
    #     print(e)
    #     exit(1)
        