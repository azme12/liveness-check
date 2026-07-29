/**
 * Trustanova Web SDK (browser)
 *
 * Usage:
 *   <script src="https://YOUR_APP/sdk/v1.js"></script>
 *   <div id="trustanova-root"></div>
 *   <script>
 *     const trustanova = new Trustanova({
 *       apiKey: 'pk_test_...',
 *       hostedBase: 'https://YOUR_APP',
 *     });
 *     trustanova.mount('#trustanova-root', { token: 'vfy_...' });
 *   </script>
 */
(function (global) {
  "use strict";

  function resolveEl(selector) {
    if (!selector) return null;
    if (typeof selector === "string") return document.querySelector(selector);
    return selector;
  }

  function Trustanova(options) {
    options = options || {};
    this.apiKey = options.apiKey || options.publishableKey || "";
    this.environment = options.environment || "test";
    this.hostedBase = (options.hostedBase || options.origin || "").replace(/\/$/, "");
    this.apiBase = (options.apiBase || "").replace(/\/$/, "");
  }

  Trustanova.prototype._hosted = function () {
    if (this.hostedBase) return this.hostedBase;
    if (typeof window !== "undefined" && window.location) return window.location.origin;
    return "";
  };

  /**
   * Mount hosted verification UI into a container (iframe).
   * @param {string|HTMLElement} selector
   * @param {{ token: string, height?: string|number }} mountOptions
   */
  Trustanova.prototype.mount = function (selector, mountOptions) {
    var el = resolveEl(selector);
    if (!el) throw new Error("Trustanova.mount: target not found");
    mountOptions = mountOptions || {};
    var token = mountOptions.token || mountOptions.sessionToken || mountOptions.verificationToken;
    if (!token) throw new Error("Trustanova.mount: token is required (from Start verification / SDK method)");

    var height = mountOptions.height || 720;
    if (typeof height === "number") height = height + "px";

    var src =
      this._hosted() +
      "/verify/" +
      encodeURIComponent(token) +
      "?embed=1" +
      (this.apiKey ? "&pk=" + encodeURIComponent(this.apiKey) : "") +
      (this.environment ? "&env=" + encodeURIComponent(this.environment) : "");

    var iframe = document.createElement("iframe");
    iframe.src = src;
    iframe.title = "Trustanova identity verification";
    iframe.allow = "camera *; microphone *; fullscreen *";
    iframe.setAttribute("allowfullscreen", "true");
    iframe.style.cssText =
      "width:100%;height:" +
      height +
      ";border:0;border-radius:12px;background:#fff;display:block;";

    el.innerHTML = "";
    el.appendChild(iframe);

    return {
      token: token,
      iframe: iframe,
      unmount: function () {
        el.innerHTML = "";
      },
    };
  };

  /**
   * Open hosted verification in a new tab/window.
   */
  Trustanova.prototype.open = function (token) {
    if (!token) throw new Error("Trustanova.open: token is required");
    var url = this._hosted() + "/verify/" + encodeURIComponent(token);
    return window.open(url, "_blank", "noopener,noreferrer");
  };

  global.Trustanova = Trustanova;
})(typeof window !== "undefined" ? window : this);
