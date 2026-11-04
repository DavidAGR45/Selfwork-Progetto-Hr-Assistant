// Forza l'aggiornamento immediato del favicon della scheda del browser con la volpe
// Bypassa la cache locale persistente di Chrome/Edge/Firefox
(function () {
  function forceFoxFavicon() {
    let link = document.querySelector("link[rel*='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "shortcut icon";
      document.getElementsByTagName("head")[0].appendChild(link);
    }
    link.type = "image/png";
    link.href = "/public/favicon-32x32.png?v=" + new Date().getTime();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", forceFoxFavicon);
  } else {
    forceFoxFavicon();
  }
})();

