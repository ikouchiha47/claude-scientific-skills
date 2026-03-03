import { useMemo } from 'preact/hooks';
import { marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import markedKatex from 'marked-katex-extension';
import hljs from 'highlight.js';
import DOMPurify from 'dompurify';
import 'highlight.js/styles/github-dark.css';

marked.use(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
      }
      return code;
    },
  })
);

marked.use(markedKatex({ throwOnError: false }));

const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'u', 'del',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img',
  'table', 'thead', 'tbody', 'tr', 'td', 'th',
  'span', 'div', 'math', 'semantics', 'mrow', 'mi', 'mo', 'mn',
  'msup', 'msub', 'mfrac', 'msqrt', 'mover', 'munder',
  'annotation',
];

export function Markdown({ content }) {
  const html = useMemo(() => {
    if (!content) return '';
    const raw = marked(content);
    return DOMPurify.sanitize(raw, {
      ALLOWED_TAGS,
      ALLOWED_ATTR: ['href', 'title', 'src', 'alt', 'class', 'id', 'style', 'aria-hidden'],
      ALLOW_DATA_ATTR: false,
    });
  }, [content]);

  return <div class="message-content" dangerouslySetInnerHTML={{ __html: html }} />;
}
