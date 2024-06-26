from enum import Enum, auto
import re
import os
import html.parser as parser
import time
import argparse

class env(Enum):
    document = auto()
    figure = auto()
    itemize = auto()
    enumerate = auto()
    table = auto()
    minted = auto()
    equation = auto()

INFO = '\033[0;37;42mInfo\033[0m '
WARN = '\033[0;37;43mWarning\033[0m '
ERROR = '\033[0;37;41mError\033[0m '

class MdHtmlParser(parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag = None
        self.attrs = None
    
    def handle_starttag(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)

def has_html(line):
    """
    检查给定的字符串是否包含 HTML 标签。
    """
    html_pattern = r'<[^>]+>'
    return bool(re.search(html_pattern, line))

def arg_parser():
    parser = argparse.ArgumentParser(description='Convert markdown to latex')
    parser.add_argument('--md-file', type=str, default='report.md', help='The markdown file to be converted')
    parser.add_argument('--tex-file', type=str, help='The output tex file')
    parser.add_argument('--template', type=str, help='The template tex file')
    parser.add_argument('--figure-pos', type=str, default='ht', help='The position of the figure')
    parser.add_argument('--table-pos', type=str, default='ht', help='The position of the table')
    parser.add_argument('-o', action='store_true', help='Overwrite the existing tex file')
    parser.add_argument('-v', action='store_true', help='Use VLOOK style cross-reference, else pandoc style')
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
            ret_table = f'\\begin{{table}}[' + args.table_pos + f']\n    \centering\n    \\caption{{{caption}}}\n    \\begin{{tabular}}' + '{'
        else:
            ret_table = f'\\begin{{table}}[' + args.table_pos + f']\n    \centering\n    \\begin{{tabular}}' + '{'
        aligns = re.findall(r':?-+:?|:-+|-+:', alignment)
        for align in aligns:
            if align.startswith(':') and align.endswith(':'):
                ret_table += 'c'
            elif align.endswith(':'):
                ret_table += 'r'
            else:
                ret_table += 'l'
        ret_table += '}\n        \\toprule\n'
        # change the header to bold
        ret_header = re.sub(r'^\||\|$', '', re.sub(r'\|', ' & ', header))
        ret_header = re.sub(r'^\s*&|&\s*$', '', re.sub(r'\|', ' & ', header))
        ret_header = re.sub(r'[^&]+', replace_func, ret_header)
        ret_table += '        ' + ret_header + ' \\\\\n        \\midrule\n'
        for i in range(len(body) - 1):
            ret_body = re.sub(r'^\||\|$', '', re.sub(r'\|', ' & ', body[i]))
            ret_body = re.sub(r'^\s*&|&\s*$', '', re.sub(r'\|', ' & ', body[i]))
            # ret_body = re.sub(r'[^&]+', replace_func, ret_body)
            ret_table += '        ' + ret_body + ' \\\\\n'
        if label:
            ret_table += f'        \\bottomrule\n    \end{{tabular}}\n    \label{{{label}}}\n\end{{table}}\n'
        else:
            ret_table += '        \\bottomrule\n    \end{tabular}\n\end{table}\n'
        ret_tables.append(ret_table)
    return ret_tables

def equations_convert(equations, with_caption, args):
    ret_eqs = []
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
        ret_eq = re.sub(r'^', '    ', ret_eq, flags=re.MULTILINE)
        ret_eq = "\\begin{equation}\n" + ret_eq + "\n\\end{equation}"
        ret_eqs.append(ret_eq)
    return ret_eqs

def md_to_tex(md_content, args):

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
            if env_stack[-1] != env.minted:
                lang = re.match(r'^\s*```(\w+)', tex_line).group(1)
                tex_content += f'\\begin{{minted}}{{{lang}}}\n'
                env_stack.append(env.minted)
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

        # 如果当前处于代码块或公式块中，则直接将当前行加入tex_content
        if env_stack[-1] in [env.equation, env.minted]:
            tex_content += tex_line + '\n'
            continue

        # *==label==* -> \label{label}
        tex_line = re.sub(r'\*==(.*?)==\*', r'\\label{\1}', tex_line)

        # **text** -> \textbf{text}
        tex_line = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', tex_line)

        # *text* -> \textit{text}
        tex_line = re.sub(r'\*(.*?)\*', r'\\textit{\1}', tex_line)

        # _text_ -> \textit{text}
        # tex_line = re.sub(r'_(.*?)_', r'\\textit{\1}', tex_line)

        # `code` -> \mintinline{code}
        tex_line = re.sub(r'`(.*?)`', r'\\mintinline{text}|\1|', tex_line)

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
            tex_line = re.sub(r'[^\\]%', r'\\%', tex_line)

        # [@reference] -> \cite{reference}
        tex_line = re.sub(r'\[@(.*?)\]', r'\\cite{\1}', tex_line)

        # [#label] -> \ref{label}
        tex_line = re.sub(r'\[#(.*?)\]', r'\\ref{\1}', tex_line)
        
        # 处理图片
        # ![label](img_path "caption") -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n    \caption{caption}\n    \label{label}\n\end{figure}
        tex_line = re.sub(r'!\[(.*?)\]\((.*?)\s*"(.*?)"\)', r'\\begin{figure}[' + args.figure_pos + r']\n    \\centering\n    \\includegraphics[width=\\textwidth]{\2}\n    \\caption{\3}\n    \\label{\1}\n\\end{figure}', tex_line)
        # ![label](img_path) -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n    \label{label}\n\end{figure}
        tex_line = re.sub(r'!\[(.*?)\]\((.*?)\)', r'\\begin{figure}[' + args.figure_pos + r']\n    \\centering\n    \\includegraphics[width=\\textwidth]{\2}\n    \\label{\1}\n\\end{figure}', tex_line)
        # ![](img_path "caption") -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n    \caption{caption}\\n\end{figure}
        tex_line = re.sub(r'!\[\]\((.*?)\s*"(.*?)"\)', r'\\begin{figure}[' + args.figure_pos + r']\n    \\centering\n    \\includegraphics[width=\\textwidth]{\1}\n    \\caption{\2}\n\\end{figure}', tex_line)
        # ![](img_path) -> \begin{figure}[args.figure_pos]\n    \centering\n    \includegraphics[width=\textwidth]{img_path}\n\end{figure}
        tex_line = re.sub(r'!\[\]\((.*?)\)', r'\\begin{figure}[' + args.figure_pos + r']\n    \\centering\n    \\includegraphics[width=\\textwidth]{\1}\n\\end{figure}', tex_line)

        # [label](url) -> \href{url}{label}
        tex_line = re.sub(r'\[(.*?)\]\((.*?)\)', r'\\href{\2}{\1}', tex_line)

        # HTML标签处理
        if has_html(tex_line):
            # 将tex_line中的百分数转化为小数
            # tex_line = re.sub(r'(\d+)%', r'\1\%', tex_line)
            html_parser = MdHtmlParser()
            html_parser.feed(tex_line)
            tag = html_parser.tag
            attrs = html_parser.attrs
            html_line = ''
            if tag == 'img':
                if 'src' not in attrs:
                    print(WARN + 'The img tag must have a src attribute, replace it with blank')
                    tex_line = re.sub(r'<[^>]+>', '', tex_line)
                else:
                    html_line = r'\begin{figure}[' + args.figure_pos + ']\n    \centering\n    \includegraphics[width='
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
                        html_line += f'    \caption{{{attrs["title"]}}}\n'
                    if 'alt' in attrs:
                        html_line += f'    \label{{{attrs["alt"]}}}\n'
                    html_line += r'\end{figure}'
            else:
                print(WARN + f'Unsupported HTML tag: {tag}, replace it without html format')
                html_line = re.sub(r'<[^>]+>', '', tex_line)

            tex_line = html_line


        # 处理无序列表
        if md_line.startswith('- '):
            if env_stack[-1] != env.itemize:
                tex_content += '\\begin{itemize}\n'
                env_stack.append(env.itemize)
            tex_line = re.sub(r'^\s*-\s+(.*)', r'    \\item \1', tex_line)
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
            tex_line = re.sub(r'^\s*\d+\.\s+(.*)', r'    \\item \1', tex_line)
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
        for i in range(1, 100):
            if os.path.exists(args.tex_file):
                args.tex_file = args.tex_file.replace(f'({i}).tex', f'({i+1}).tex')
            else:
                break
        if i == 100:
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
        