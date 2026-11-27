"""Step-by-step shopping chat. The caller keeps one session per conversation."""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from urllib.parse import urlencode

STORES = {
    "Blinkit": ("https://blinkit.com/", "https://blinkit.com/s/", "q"),
    "Amazon": ("https://www.amazon.in/", "https://www.amazon.in/s", "k"),
    "Swiggy Instamart": (
        "https://www.swiggy.com/instamart",
        "https://www.swiggy.com/instamart/search",
        "query",
    ),
}
STORE_ALIASES = {
    "Blinkit": {"blinkit", "blink it", "ब्लिंकिट", "ब्लिंक इट"},
    "Amazon": {"amazon", "amazon india", "अमेज़न", "अमेजन", "एमेज़ॉन"},
    "Swiggy Instamart": {"swiggy", "instamart", "swiggy instamart", "स्विगी", "इंस्टामार्ट"},
}
YES = {"yes", "yeah", "yep", "ha", "haa", "haan", "हाँ", "हां", "हा", "जी"}
NO = {"no", "nope", "na", "naa", "nahi", "nahin", "nhi", "ना", "नहीं", "नही"}

PROMPTS = {
    "store": "Where would you like to shop? Choose Blinkit, Amazon, or Swiggy Instamart.",
    "login": "Open {store} and check your account. Are you already signed in?",
    "offer_login": "Would you like me to guide you through signing in to {store}?",
    "sign_in": "Open {store}, choose Sign in or Login, and follow the instructions on that site. Are you signed in now?",
    "sign_in_self": "Sign in on {store}, then tell me when you are signed in. Are you signed in now?",
    "items": "What would you like to buy? You can say the items as a list.",
    "item": "Open the link for {item}, choose the product and quantity you want, and add it to your cart. Did you add it?",
    "cart": "Are all the items you want in your cart?",
    "offer_checkout": "Would you like help going through checkout?",
    "checkout_cart": "Open your cart and check the products, quantities, and total. Is the cart correct?",
    "checkout_address": "Proceed to checkout and check your delivery address and delivery options. Are they correct?",
    "checkout_payment": "Choose a payment method on {store} and review the final total. Are you ready to submit payment?",
    "payment_ready": "Complete payment yourself on {store} when you are ready. Check the order confirmation there.",
    "done": "Okay, the shopping guide is finished.",
}


@dataclass(frozen=True)
class ShoppingSession:
    step: str
    store: str | None = None
    items: tuple[str, ...] = ()
    item_index: int = 0


def _normalized(text: str) -> str:
    return " ".join(text.casefold().strip(" .,!?:;।").split())


def _store(text: str) -> str | None:
    text = _normalized(text)
    matches = [
        store for store, aliases in STORE_ALIASES.items()
        if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) for alias in aliases)
    ]
    return matches[0] if len(matches) == 1 else None


def _items(names) -> tuple[str, ...]:
    return tuple(dict.fromkeys(name.strip() for name in names if name.strip()))


def start_shopping(source: str = "", items: tuple[str, ...] = ()) -> ShoppingSession:
    """Use the store and item names extracted from the initial shopping request."""
    store = _store(source)
    return ShoppingSession("login" if store else "store", store, _items(items))


def shopping_reply(
    session: ShoppingSession,
    answer: str,
    *,
    extract_items: Callable[[str], list[str]] | None = None,
) -> ShoppingSession:
    """Accept a button value or transcribed answer and advance at most one step."""
    if _normalized(answer) in {"cancel", "stop shopping", "रद्द करो"}:
        return replace(session, step="done")
    if session.step in {"done", "payment_ready"}:
        return session
    if session.step == "store":
        store = _store(answer)
        return replace(session, step="login", store=store) if store else session
    if session.step == "items":
        if not _normalized(answer) or _normalized(answer) in YES | NO:
            return session
        if extract_items is not None:
            items = _items(extract_items(answer))
            return replace(session, step="item", items=items, item_index=0) if items else session
        # Voice transcripts often start with a hesitation and a request phrase.
        spoken_items = re.sub(r"^(?:(?:h+m+|u+m+|u+h+|yes|yeah|yep|haan|okay|ok|please|हाँ|हां|जी|हम्म|उम्)[, .।]+)+", "", answer.strip(), flags=re.IGNORECASE)
        spoken_items = re.sub(
            r"^(?:(?:i (?:want|need|would like) to )?(?:buy|order|get)\s+(?:(?:a|an|some)\s+)?|मुझे\s+)",
            "", spoken_items, flags=re.IGNORECASE,
        )
        spoken_items = re.sub(r"\s+(?:please|चाहिए|खरीदना है)[.!?।]*$", "", spoken_items, flags=re.IGNORECASE)
        items = _items(part.strip(" .!?।") for part in re.split(
            r"\s*(?:[,;\n]|\band\b|\bऔर\b)\s*", spoken_items, flags=re.IGNORECASE,
        ))
        items = tuple(item for item in items if _normalized(item) not in YES | NO)
        if items:
            return replace(session, step="item", items=items, item_index=0)
        return session

    answer = _normalized(answer)
    if answer not in YES | NO:
        return session
    confirmed = answer in YES
    if session.step in {"login", "sign_in", "sign_in_self"} and confirmed:
        return replace(session, step="item" if session.items else "items")
    if session.step == "item" and confirmed:
        index = session.item_index + 1
        return replace(session, item_index=index, step="item" if index < len(session.items) else "cart")

    transitions = {
        "login": (None, "offer_login"),
        "offer_login": ("sign_in", "sign_in_self"),
        "sign_in": (None, "sign_in"),
        "sign_in_self": (None, "offer_login"),
        "item": (None, "item"),
        "cart": ("offer_checkout", "item"),
        "offer_checkout": ("checkout_cart", "done"),
        "checkout_cart": ("checkout_address", "checkout_cart"),
        "checkout_address": ("checkout_payment", "checkout_address"),
        "checkout_payment": ("payment_ready", "checkout_payment"),
    }
    step = transitions[session.step][0 if confirmed else 1]
    return replace(session, step=step, item_index=0 if session.step == "cart" and not confirmed else session.item_index)


def shopping_message(session: ShoppingSession) -> dict:
    """Return chat text, choices, and a retailer link for the current step."""
    step = session.step
    item = session.items[session.item_index] if step == "item" else None
    done = step in {"done", "payment_ready"}
    choices = list(STORES) if step == "store" else [] if step == "items" or done else ["Yes", "No"]
    result = {"step": step, "response": PROMPTS[step].format(store=session.store, item=item),
              "choices": choices, "done": done, "action": None}
    if session.store and step in {"login", "sign_in", "sign_in_self", "item", "checkout_cart"}:
        home, search, query = STORES[session.store]
        # A retailer search avoids guessing a SKU or adding a product the user did not choose.
        url = f"{search}?{urlencode({query: item})}" if item else home
        result["action"] = {"label": f"Find {item} on {session.store}" if item else f"Open {session.store}",
                            "url": url}
        if item is not None and session.item_index == 0:
            result["actions"] = [
                {"label": f"Find {name} on {session.store}", "url": f"{search}?{urlencode({query: name})}"}
                for name in session.items
            ]
    return result
