"""Test double only. A real MAF chat client whose replies come from a script, so workflow logic runs offline.

Rules are (substring of the agent's system prompt or message, reply or callable). Application code never imports this.
"""
from __future__ import annotations

from agent_framework import BaseChatClient, ChatMiddlewareLayer, ChatResponse, ChatResponseUpdate, Content, FunctionInvocationLayer, Message, ResponseStream


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, rules):
        super().__init__()
        self.rules = rules
        self.calls: list[str] = []

    def _reply(self, messages, options) -> str:
        text = str(options.get("instructions") or "") + "\n" + "\n".join(str(m.text) for m in messages)
        self.calls.append(text)
        for needle, reply in self.rules:
            if needle in text:
                return reply(text) if callable(reply) else reply
        raise AssertionError(f"No scripted reply for: {text[-400:]}")

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        reply = self._reply(messages, options)
        if isinstance(reply, dict) and "cut_off" in reply:  # a reply stopped by the token limit
            async def cut_off():
                return ChatResponse(messages=[Message(role="assistant", contents=[Content.from_text(reply["cut_off"])])], finish_reason="length")

            return cut_off()
        if isinstance(reply, dict):  # a tool call, for agents that act through tools
            contents = [Content.from_function_call(call_id="call_1", name=reply["call"], arguments=reply["args"])]

            async def call_tool():
                return ChatResponse(messages=[Message(role="assistant", contents=contents)])

            return call_tool()
        if stream:
            async def updates():
                yield ChatResponseUpdate(contents=[Content.from_text(reply)], role="assistant")

            return ResponseStream(updates(), finalizer=lambda items: ChatResponse.from_updates(items))

        async def respond():
            return ChatResponse(messages=[Message(role="assistant", contents=[Content.from_text(reply)])], usage_details={"input_token_count": 10, "output_token_count": 5})

        return respond()
