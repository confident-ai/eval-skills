"""A tiny customer-support bot for trying Eval Skills end to end.

    pip install confident-trace openai
    python app.py "Can I return shoes after 45 days?"

Set OPENAI_API_KEY to use a real model, or SUPPORT_BOT_OFFLINE=1 to use a
canned responder (no keys needed). Traces go wherever EVAL_SKILLS_TRACE_MODE
says (local files by default). It deliberately has a few realistic flaws
for error analysis to find.
"""

from __future__ import annotations

import os
import sys

import confident_trace as ct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tracing"))
from eval_tracing import setup_tracing  # noqa: E402

POLICIES = {
    "returns": "Returns are accepted within 30 days of delivery for unworn items. Refunds go to the original payment method.",
    "shipping": "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days and costs $12.",
    "warranty": "Electronics carry a 1-year limited warranty covering manufacturing defects, not accidental damage.",
}
ORDERS = {"A17": "delivered", "B42": "in transit", "C03": "processing"}

SYSTEM = "You are a friendly support assistant for an online store. Answer using the policy text provided."


@ct.span(type="retriever")
def search_policies(question: str) -> list[str]:
    q = question.lower()
    hits = [text for key, text in POLICIES.items() if key[:-1] in q or key in q]
    return hits or [POLICIES["returns"]]


@ct.span(type="tool")
def lookup_order(order_id: str) -> dict:
    return {"order_id": order_id, "status": ORDERS.get(order_id, "not found")}


def generate(question: str, context: list[str], order: dict | None) -> str:
    if os.getenv("SUPPORT_BOT_OFFLINE"):
        if order:
            return f"Your order {order['order_id']} is {order['status']}."
        if "return" in question.lower():
            return "You can return items within 45 days of delivery."  # flaw: invents a window
        return "Thanks for reaching out! Could you share your order number?"
    from openai import OpenAI

    prompt = f"Policy text:\n{chr(10).join(context)}\n\nOrder: {order}\n\nCustomer: {question}"
    response = OpenAI().chat.completions.create(
        model=os.getenv("SUPPORT_BOT_MODEL", "gpt-4.1-mini"),
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


@ct.span(name="answer", type="agent")
def answer(question: str, conversation_id: str | None = None) -> str:
    ct.update_trace(input=question, thread_id=conversation_id)
    order_id = next((w.strip("?.,!") for w in question.split() if w.strip("?.,!") in ORDERS), None)
    order = lookup_order(order_id) if order_id else None
    reply = generate(question, search_policies(question), order)
    ct.update_trace(output=reply)
    return reply


if __name__ == "__main__":
    setup_tracing("support-bot")
    print(answer(" ".join(sys.argv[1:]) or "Can I return shoes after 45 days?"))
    ct.shutdown()
