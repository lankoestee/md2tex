from html import parser

# '<img src="./figure/latex_bird.png" alt="fig1" title="Latex Bird" style="zoom:50%;" /><img src="./figure/latex_bird.png" alt="fig2" title="Latex Bird" style="zoom:50%;" />'
class MyHTMLParser(parser.HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            print(dict(attrs))
            attrs = dict(attrs)

htmlparser = MyHTMLParser()
htmlparser.feed('<img src="./figure/latex_bird.png" alt="fig1" title="Latex Bird" style="zoom:50%;" />')
print('---')
htmlcontent = '<img src="./figure/latex_bird.png" alt="fig2" title="Latex Bird" style="zoom:50%;" />'
htmlparser.feed(htmlcontent)
print(htmlcontent)
