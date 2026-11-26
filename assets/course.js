(() => {
  const ready = (fn) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  };

  ready(() => {
    // Ensure keyboard access for horizontally scrollable code blocks
    document.querySelectorAll("pre").forEach((pre) => {
      if (!pre.hasAttribute("tabindex")) {
        pre.setAttribute("tabindex", "0");
      }
    });

    // Narrow-viewport sidenote toggles
    document.querySelectorAll(".sidenote-toggle").forEach((btn) => {
      const targetId = btn.getAttribute("aria-controls");
      const note = targetId ? document.getElementById(targetId) : null;
      if (!note) return;
      btn.addEventListener("click", () => {
        if (window.matchMedia("(min-width: 1060px)").matches) return;
        const expanded = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!expanded));
        note.hidden = expanded;
      });
    });

    // Mermaid dark theme
    if (window.mermaid) {
      window.mermaid.initialize({
        startOnLoad: true,
        theme: "dark",
        securityLevel: "loose",
      });
    }

    // KaTeX auto-render
    if (window.renderMathInElement) {
      window.renderMathInElement(document.body, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false },
          { left: "\\[", right: "\\]", display: true },
        ],
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"],
        throwOnError: false,
      });
    }

    // Interactive fill-in-the-blank exercises
    document.querySelectorAll(".exercise-box").forEach((box) => {
      const inputs = Array.from(box.querySelectorAll(".blank-input"));
      const feedback = box.querySelector(".exercise-feedback");
      const checkBtn = box.querySelector("[data-action='check']");
      const revealBtn = box.querySelector("[data-action='reveal']");
      const resetBtn = box.querySelector("[data-action='reset']");
      const hintPrompt = box.dataset.hint || "Check each highlighted blank.";
      const successPrompt = box.dataset.success || "All blanks verified!";

      const checkAnswers = () => {
        let allCorrect = true;
        const firstHints = [];
        inputs.forEach((input) => {
          const accepted = (input.dataset.answer || "")
            .split("||")
            .map((v) => v.trim());
          const actual = input.value.trim();
          const ok = accepted.includes(actual);
          input.classList.toggle("is-correct", ok);
          input.classList.toggle("is-wrong", !ok);
          if (!ok) {
            allCorrect = false;
            if (input.dataset.hint) {
              firstHints.push(input.dataset.hint);
            }
          }
        });

        if (!feedback) return;
        feedback.hidden = false;
        feedback.classList.toggle("is-success", allCorrect);
        feedback.classList.toggle("is-error", !allCorrect);
        feedback.textContent = allCorrect
          ? successPrompt
          : firstHints[0] || hintPrompt;
      };

      if (checkBtn) {
        checkBtn.addEventListener("click", checkAnswers);
      }

      if (revealBtn) {
        revealBtn.addEventListener("click", () => {
          inputs.forEach((input) => {
            const firstAnswer = (input.dataset.answer || "").split("||")[0].trim();
            input.value = firstAnswer;
            input.classList.remove("is-wrong");
            input.classList.add("is-correct");
          });
          if (feedback) {
            feedback.hidden = false;
            feedback.classList.remove("is-error");
            feedback.classList.add("is-success");
            feedback.textContent = successPrompt;
          }
        });
      }

      if (resetBtn) {
        resetBtn.addEventListener("click", () => {
          inputs.forEach((input) => {
            input.value = "";
            input.classList.remove("is-correct", "is-wrong");
          });
          if (feedback) {
            feedback.hidden = true;
            feedback.textContent = "";
            feedback.classList.remove("is-success", "is-error");
          }
        });
      }
    });

    // Interactive multiple-choice quizzes
    document.querySelectorAll(".quiz-box").forEach((quiz) => {
      quiz.querySelectorAll(".quiz-question").forEach((questionEl) => {
        const buttons = Array.from(questionEl.querySelectorAll(".quiz-option"));
        const explainBox = questionEl.querySelector(".quiz-explain");
        const wrongHint = questionEl.dataset.wrongHint || "Try reviewing the section above.";

        buttons.forEach((btn) => {
          btn.addEventListener("click", () => {
            const isCorrect = btn.dataset.correct === "true";
            buttons.forEach((other) => {
              other.classList.remove("is-selected", "is-correct", "is-wrong");
              other.setAttribute("aria-pressed", "false");
            });
            btn.classList.add("is-selected", isCorrect ? "is-correct" : "is-wrong");
            btn.setAttribute("aria-pressed", "true");
            if (explainBox) {
              explainBox.hidden = false;
              const explainText = btn.dataset.explain || "";
              explainBox.textContent = isCorrect
                ? `Correct — ${explainText}`
                : `Not quite — ${explainText || wrongHint}`;
            }
          });
        });
      });
    });
  });
})();
