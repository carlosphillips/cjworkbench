// ---- Utilities ---
import * as Cookies from "js-cookie"

export function goToUrl(url) {
  window.location.href = url;
}

// Current CSRF token
export const csrfToken = Cookies.get('csrftoken');

// Find the parameter value by its id name
export function findParamValByIdName(wfm, paramValIdName) {
  return wfm.parameter_vals.find((parameterVal) => {
        return parameterVal.parameter_spec.id_name === paramValIdName;
    });
}

// Gets the letter coordinate of a column from its index within the column names array
export function idxToLetter(idx) {
  var letters = '';
  var cidx = parseInt(idx);
  cidx += 1;
  do {
    cidx -= 1;
    letters = String.fromCharCode(cidx % 26 + 65) + letters;
    cidx = Math.floor(cidx / 26);
  } while(cidx > 0)
  return letters;
}

// Log to Intercom, if installed
export function logUserEvent(name, metadata) {
  if (!window.APP_ID) return

  // If we're in a lesson, drop the event. (Use logUserEventEvenInLesson
  // to override.)
  //
  // https://www.pivotaltracker.com/story/show/160041803
  if (window.initState && window.initState.lessonData) return

  window.Intercom('trackEvent', name, metadata)
}

export function logUserEventEvenInLesson(name, metadata) {
  if (!window.APP_ID) return

  window.Intercom('trackEvent', name, metadata)
}

export function timeDifference (start, end) {
  const ms = new Date(end) - new Date(start)
  const minutes = Math.floor(ms / 1000 / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  const years = Math.floor(days / 365.25)

  if (years > 0) {
    if (years == 1) {
      return "1y ago";
    } else {
      return "" + years + "y ago";
    }
  }
  else if (days > 0) {
    if (days == 1) {
      return "1d ago";
    } else {
      return "" + days + "d ago";
    }
  }
  else if (hours > 0) {
    if (hours == 1) {
      return "1h ago";
    } else {
      return "" + hours + "h ago";
    }
  }
  else if (minutes > 0) {
    if (minutes == 1) {
      return "1m ago";
    } else {
      return "" + minutes + "m ago";
    }
  }
  else {
    return "now";
  }
}

export function escapeHtml(str) {
  str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  return str;
}

/**
 * Scroll `containerEl` vertically by the smallest amount possible to put
 * `el` in view.
 *
 * Set the container CSS `scroll-behavior: smooth` to make this transition
 * look nice.
 *
 * @param el Element we want to focus
 * @param containerEl Element we'll set scrollTop on so it contains el
 * @param marginTop Minimum number of pixels between containerEl.top and el.top
 * @param marginBottom Minimum number of pixels between containerEl.bottom and el.bottom
 */
export function scrollTo(el, containerEl, marginTop, marginBottom) {
  if (marginTop === undefined) marginTop = 10
  if (marginBottom === undefined) marginBottom = 10

  const elRect = el.getBoundingClientRect()
  const containerRect = containerEl.getBoundingClientRect()

  // Calculate dy: how much do we need to add to containerEl.scrollTop to
  // make el go where we want it to go?
  let dy = 0 // Prefer not to scroll
  if (elRect.bottom + marginBottom > containerRect.bottom) {
    // Scroll down if we need to.
    // We do this before up because some els might be taller than containerEl,
    // and in that case we want scroll-up to override scroll-down (because the
    // top of el is more important than the bottom).
    dy += (elRect.bottom + marginBottom - containerRect.bottom)
  }
  if (dy + elRect.top - marginTop < containerRect.top) {
    // Scroll up if we need to.
    dy -= (containerRect.top - (elRect.top - marginTop))
  }

  containerEl.scrollTop += dy
}
