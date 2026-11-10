/*
 * Theme menu of the tbottest documentation.
 *
 * build-docs.sh --all-themes builds sphinx_rtd_theme into output/ and
 * every other theme into output/<theme>/ (DOC_THEMES in conf.py). conf.py
 * passes the theme of the current build in data-doc-theme; the menu opens
 * the current page in another theme.
 */
(function () {
    "use strict";

    var themes = [
        { key: "rtd", dir: "", label: "Read the Docs" },
        { key: "piccolo", dir: "piccolo/", label: "Piccolo" },
        { key: "cloud", dir: "cloud/", label: "Cloud" },
        { key: "nefertiti", dir: "nefertiti/", label: "Nefertiti" },
    ];

    var script = document.currentScript;
    var current = script.getAttribute("data-doc-theme");
    var currentdir = "";
    themes.forEach(function (theme) {
        if (theme.key === current) {
            currentdir = theme.dir;
        }
    });

    // root of this build: the URL of this script without _static/...
    var src = script.src.split("?")[0];
    var buildroot = src.slice(0, src.lastIndexOf("_static/"));
    var siteroot = buildroot.slice(0, buildroot.length - currentdir.length);
    var page = "";
    if (window.location.href.indexOf(buildroot) === 0) {
        page = window.location.href.slice(buildroot.length);
    }

    function addMenu() {
        var box = document.createElement("div");
        box.style.cssText =
            "position: fixed; right: 1em; bottom: 1em; z-index: 1000;" +
            "padding: 0.3em 0.6em; border: 1px solid #888; border-radius: 4px;" +
            "background: #fff; color: #000; font: 13px sans-serif;";

        var label = document.createElement("label");
        label.appendChild(document.createTextNode("Theme "));

        var select = document.createElement("select");
        themes.forEach(function (theme) {
            var option = document.createElement("option");
            option.value = theme.dir;
            option.textContent = theme.label;
            option.selected = theme.key === current;
            select.appendChild(option);
        });
        select.addEventListener("change", function () {
            window.location.href = siteroot + select.value + page;
        });

        label.appendChild(select);
        box.appendChild(label);
        document.body.appendChild(box);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", addMenu);
    } else {
        addMenu();
    }
})();
