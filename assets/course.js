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

    // Copy buttons for code and command blocks (Invoker Commands + click fallback)
    const copyTimers = new WeakMap();
    let lastCopyMessage = "";

    const legacyCopy = (text) => {
      const previousFocus = document.activeElement;
      const field = Object.assign(document.createElement("textarea"), { value: text });
      field.setAttribute("readonly", "");
      field.style.cssText = "position:fixed;inset-block-start:0;opacity:0";
      document.body.append(field);
      field.select();
      try {
        return document.execCommand("copy");
      } finally {
        field.remove();
        previousFocus?.focus({ preventScroll: true });
      }
    };

    const reportCopy = (button, ok) => {
      const tip = button.nextElementSibling;
      clearTimeout(copyTimers.get(button));
      button.removeAttribute("data-copied");
      button.removeAttribute("data-failed");
      let message = ok ? "Copied" : "Copy failed";
      if (message === lastCopyMessage) {
        message += "\u00A0";
      }
      lastCopyMessage = message;
      if (tip) {
        tip.textContent = "";
      }
      void button.offsetWidth;
      button.setAttribute(ok ? "data-copied" : "data-failed", "");
      if (tip) {
        requestAnimationFrame(() => {
          tip.textContent = message;
        });
      }
      copyTimers.set(
        button,
        setTimeout(() => {
          button.removeAttribute("data-copied");
          button.removeAttribute("data-failed");
          if (tip) {
            tip.textContent = "";
          }
        }, 2000),
      );
    };

    const copyFromTarget = async (button, target) => {
      if (!button || !target) return;
      const text = target.matches("input, textarea")
        ? target.value
        : target.innerText.trimEnd();
      if (!text.trim()) return;

      if (!navigator.clipboard?.writeText) {
        reportCopy(button, legacyCopy(text));
        return;
      }

      try {
        await navigator.clipboard.writeText(text);
        reportCopy(button, true);
      } catch {
        reportCopy(button, legacyCopy(text));
      }
    };

    if ("CommandEvent" in window) {
      document.addEventListener(
        "command",
        (event) => {
          if (event.command === "--copy") {
            copyFromTarget(event.source, event.target);
          }
        },
        true,
      );
    } else {
      document.addEventListener("click", (event) => {
        if (event.defaultPrevented) return;
        const button = event.target.closest('button[command="--copy"]');
        if (!button) return;
        const targetId = button.getAttribute("commandfor");
        const target = targetId ? document.getElementById(targetId) : null;
        if (target) {
          copyFromTarget(button, target);
        }
      });
    }

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

    // Mermaid Bench Oscilloscope dark theme
    if (window.mermaid) {
      window.mermaid.initialize({
        startOnLoad: true,
        theme: "base",
        themeVariables: {
          darkMode: true,
          background: "#151311",
          primaryColor: "#201d1a",
          primaryTextColor: "#ebe5dc",
          primaryBorderColor: "#474038",
          lineColor: "#e5a94c",
          secondaryColor: "#191715",
          tertiaryColor: "#191715",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif",
        },
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
