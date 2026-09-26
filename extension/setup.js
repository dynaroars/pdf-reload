const status = document.querySelector("#status");
browser.runtime.sendNativeMessage("local_pdf_reload", {type: "status"})
  .then(() => {
    status.textContent = "The helper is installed and ready.";
    document.querySelector("#linux").hidden = true;
  })
  .catch(() => {
    status.textContent = "The helper is not installed yet.";
  });
