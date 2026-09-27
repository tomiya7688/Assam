"""Terminal ABI and in-process message bus for ASSAM devices."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol
class Terminal(Protocol):
    name: str
    def init(self) -> None: ...
    def tick(self) -> None: ...
    def receive(self, message: Any) -> None: ...
    def shutdown(self) -> None: ...
@dataclass(frozen=True)
class Message:
    sender: str
    recipient: str
    payload: Any
class BasicTerminal:
    def __init__(self, name: str):
        if not name: raise ValueError("terminal name must not be empty")
        self.name=name; self.inbox=deque(); self.started=False; self.stopped=False
    def init(self): self.started=True
    def tick(self): pass
    def receive(self, message): self.inbox.append(message)
    def shutdown(self): self.stopped=True
class TerminalBus:
    def __init__(self): self.terminals={}; self.connections={}; self.messages=deque()
    def register(self, terminal):
        if terminal.name in self.terminals: raise ValueError(f"terminal already registered: {terminal.name}")
        self.terminals[terminal.name]=terminal; self.connections[terminal.name]=set(); terminal.init()
    def unregister(self, name):
        terminal=self.terminals.pop(name); self.connections.pop(name, None)
        for peers in self.connections.values(): peers.discard(name)
        terminal.shutdown()
    def _require(self, name):
        if name not in self.terminals: raise KeyError(f"unknown terminal: {name}")
    def connect(self, first, second):
        self._require(first); self._require(second); self.connections[first].add(second); self.connections[second].add(first)
    def disconnect(self, first, second):
        self._require(first); self._require(second); self.connections[first].discard(second); self.connections[second].discard(first)
    def send(self, sender, recipient, payload):
        self._require(sender); self._require(recipient)
        if recipient not in self.connections[sender]: raise ValueError(f"terminals are not connected: {sender} -> {recipient}")
        message=Message(sender, recipient, payload); self.messages.append(message); self.terminals[recipient].receive(message); return message
    def broadcast(self, sender, payload):
        self._require(sender); return [self.send(sender, x, payload) for x in sorted(self.connections[sender])]
    def drain_messages(self):
        result=list(self.messages); self.messages.clear(); return result