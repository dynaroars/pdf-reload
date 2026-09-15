browser.runtime.sendNativeMessage("local_pdf_reload", {type: "status"})
  .then(() => {
    document.querySelector("#status").textContent = "The helper is installed and ready.";
  })
  .catch(() => {
    document.querySelector("#status").textContent = "The helper is not installed yet.";
  });
