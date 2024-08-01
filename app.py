import gradio as gr

from md2tex import md_to_tex

class Args:
    def __init__(self, figure_pos, table_pos, spaces, code_type, have_title):
        self.figure_pos = figure_pos
        self.table_pos = table_pos
        self.spaces = spaces
        self.code_type = code_type
        self.have_title = have_title

def md_to_tex_wrapper(content, figure_pos, table_pos, spaces, code_type, have_title):
    # 将figure_pos和table_pos的列表转换为字符串
    figure_pos = "".join(figure_pos)
    table_pos = "".join(table_pos)
    args = Args(figure_pos, table_pos, spaces, code_type, have_title)
    return md_to_tex(content, args)

with gr.Blocks(theme=gr.themes.Soft(font="system-ui")) as demo:
    gr.Markdown("## Markdown to LaTeX Converter")

    with gr.Row():
        with gr.Column():
            markdown_input = gr.Textbox(lines=10, label="Markdown Input", placeholder="Enter markdown here...")
            submit_button = gr.Button("Convert", variant="primary")
        with gr.Column():
            output = gr.Textbox(label="LaTeX Output", lines=12.6, max_lines=22.6, interactive=False, placeholder="LaTeX output will appear here...", show_copy_button=True)

    with gr.Accordion(label="Advanced Options"):
        figure_pos = gr.CheckboxGroup(["H", "h", "t", "b", "p"], value=["h", "t"], label="Figure Placement")
        table_pos = gr.CheckboxGroup(["H", "h", "t", "b", "p"], value=["h", "t"], label="Table Placement")
        spaces = gr.Number(label="Indentation", value=4)
        code_type = gr.Radio(["lstlisting", "minted"], label="Code Type", value="minted")
        have_title = gr.Checkbox(label="Have Title", value=False, info="Whether the document has a title, if Ture, ‘#’ will not be translated and ‘##’ will translated into ‘\section’, else ‘#’ will be translated into ‘\section’.")

    submit_button.click(md_to_tex_wrapper, inputs=[markdown_input, figure_pos, table_pos, spaces, code_type, have_title], outputs=output, show_progress=True)

if __name__ == "__main__":
    demo.launch()