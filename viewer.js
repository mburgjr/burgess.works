// One-at-a-time viewer shared by paintings.html and poems.html.
// `render(item)` fills the page; the hash (#1, #2, ...) holds the position.
function startViewer(items, render) {
  var index = 0;
  var tabs = document.getElementById("item-tabs");

  // Every item hidden or none added yet: say so instead of an empty frame.
  if (items.length === 0) {
    document.querySelector(".viewer").hidden = true;
    document.getElementById("prev").hidden = true;
    document.getElementById("next").hidden = true;
    var empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Nothing here yet.";
    document.querySelector("main").appendChild(empty);
    return;
  }

  // One highlighter tab per item, in place of a "2 / 5" counter.
  items.forEach(function (item, i) {
    var tab = document.createElement("button");
    tab.type = "button";
    tab.textContent = i + 1;
    tab.title = item.title;
    // Starts with the number shown, so voice control's "click 3" finds it.
    tab.setAttribute("aria-label", (i + 1) + ": " + item.title);
    tab.addEventListener("click", function () { show(i); });
    tabs.appendChild(tab);
  });

  function indexFromHash() {
    var n = parseInt(location.hash.slice(1), 10);
    return n >= 1 && n <= items.length ? n - 1 : 0;
  }

  function show(newIndex) {
    index = (newIndex + items.length) % items.length;
    render(items[index], index);
    Array.prototype.forEach.call(tabs.children, function (tab, i) {
      if (i === index) tab.setAttribute("aria-current", "true");
      else tab.removeAttribute("aria-current");
    });
    // Centre the current tab when the row scrolls sideways (more items than
    // fit). scrollIntoView would scroll the whole page too.
    var tabBox = tabs.children[index].getBoundingClientRect();
    var rowBox = tabs.getBoundingClientRect();
    tabs.scrollLeft += tabBox.left - rowBox.left - (rowBox.width - tabBox.width) / 2;
    // replaceState keeps the Back button for leaving the page, not paging.
    history.replaceState(null, "", "#" + (index + 1));
  }

  if (items.length < 2) {
    document.getElementById("prev").hidden = true;
    document.getElementById("next").hidden = true;
  }
  document.getElementById("prev").addEventListener("click", function () { show(index - 1); });
  document.getElementById("next").addEventListener("click", function () { show(index + 1); });

  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowLeft") show(index - 1);
    if (event.key === "ArrowRight") show(index + 1);
  });

  var startX = null, startY = null;
  document.addEventListener("touchstart", function (event) {
    var touch = event.touches[0];
    var zoomed = window.visualViewport && visualViewport.scale > 1.01;
    // Pinches, panning a zoomed-in page, scrolling the tab row and the
    // phone's own edge-swipe gestures are not page turns.
    var nearEdge = touch.clientX < 20 || touch.clientX > window.innerWidth - 20;
    var onTabs = event.target.closest && event.target.closest(".item-tabs");
    if (event.touches.length > 1 || zoomed || nearEdge || onTabs) startX = null;
    else { startX = touch.clientX; startY = touch.clientY; }
  }, { passive: true });
  document.addEventListener("touchend", function (event) {
    if (startX === null || event.touches.length) return;
    var dx = event.changedTouches[0].clientX - startX;
    var dy = event.changedTouches[0].clientY - startY;
    startX = null;
    // Mostly-horizontal swipes only, so vertical scrolling of long poems still works.
    if (Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy)) show(index + (dx < 0 ? 1 : -1));
  }, { passive: true });

  window.addEventListener("hashchange", function () { show(indexFromHash()); });
  show(indexFromHash());
}
