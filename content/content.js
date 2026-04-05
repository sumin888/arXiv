// Runs on arxiv.org/abs/* pages.
// Extracts paper metadata from the DOM and sends it to the background worker.

(function extractPaper() {
  const paper = parsePaperPage();
  if (!paper) return;

  chrome.runtime.sendMessage({ type: "PAPER_DETECTED", paper });
})();

function parsePaperPage() {
  // arXiv ID from URL: /abs/2301.07041  or  /abs/cs/0601001
  const idMatch = window.location.pathname.match(/\/abs\/(.+)/);
  if (!idMatch) return null;
  const arxivId = idMatch[1].trim();

  // Title
  const titleEl = document.querySelector("h1.title");
  const title = titleEl
    ? titleEl.innerText.replace(/^Title:\s*/i, "").trim()
    : document.title.trim();

  // Authors
  const authorEls = document.querySelectorAll(".authors a");
  const authors = Array.from(authorEls).map((a) => a.innerText.trim());

  // Abstract
  const abstractEl = document.querySelector("blockquote.abstract");
  const abstract = abstractEl
    ? abstractEl.innerText.replace(/^Abstract:\s*/i, "").trim()
    : "";

  // Subjects / categories
  const subjectEl = document.querySelector(".subjects");
  const subjects = subjectEl ? subjectEl.innerText.trim() : "";

  // Submission date
  const dateEl = document.querySelector(".dateline");
  const dateText = dateEl ? dateEl.innerText.trim() : "";

  return { arxivId, title, authors, abstract, subjects, dateText, url: window.location.href };
}
