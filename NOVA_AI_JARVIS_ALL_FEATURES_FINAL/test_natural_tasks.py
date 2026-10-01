from __future__ import annotations

import sys
from pathlib import Path
from core.orchestrator import NovaOrchestrator
import tools.everything_file_finder as eff

def run_tests():
    print("=== INITIALIZING NOVA ORCHESTRATOR FOR TEST SUITE ===")
    orc = NovaOrchestrator()
    print("Action count:", len(orc.registry.names()))
    assert "learning_resources" in orc.registry.names(), "learning_resources action must be registered!"

    # Populate mock files in everything_file_finder so tests work deterministically on any PC
    eff._last = [
        r"C:\Users\User\Documents\DSA_Notes.pdf",
        r"C:\Users\User\Documents\DSA_Assignment.pdf",
        r"C:\Users\User\Documents\DSA_Final.pdf",
        r"C:\Users\User\Documents\DSA_CheatSheet.pdf",
    ]
    orc.task_manager.set_file_results(eff._last)

    print("\n--- TEST 1: 'open google colab in chrome' ---")
    reply, used = orc.handle("open google colab in chrome")
    print(f"Reply: {reply[:80]}... | Provider: {used}")
    assert "colab" in reply.lower() or "google colab" in reply.lower() or "opened" in reply.lower() or "http" in reply.lower(), "Colab must be resolved to browser navigation!"

    print("\n--- TEST 2: 'open youtube' ---")
    reply, used = orc.handle("open youtube")
    print(f"Reply: {reply[:80]}... | Provider: {used}")
    assert "youtube" in reply.lower() or "opened" in reply.lower(), "YouTube must be resolved to browser navigation!"

    print("\n--- TEST 3: 'find my DSA PDF' ---")
    reply, used = orc.handle("find my DSA PDF")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert "1." in reply or "01." in reply, "Must display numbered file choices!"

    print("\n--- TEST 4: '3' or 'file 3' selection ---")
    # Verify resolve_file_ref
    selected = orc.task_manager.resolve_file_ref("3")
    print(f"Resolved '3': {selected}")
    assert selected == r"C:\Users\User\Documents\DSA_Final.pdf", "Should resolve to 3rd result!"

    selected_file_3 = orc.task_manager.resolve_file_ref("file 3")
    print(f"Resolved 'file 3': {selected_file_3}")
    assert selected_file_3 == r"C:\Users\User\Documents\DSA_Final.pdf", "Should resolve 'file 3'!"

    selected_name = orc.task_manager.resolve_file_ref("DSA_Final.pdf")
    print(f"Resolved 'DSA_Final.pdf': {selected_name}")
    assert selected_name == r"C:\Users\User\Documents\DSA_Final.pdf", "Should resolve by name!"

    print("\n--- TEST 5: 'I want to learn DSA' ---")
    reply, used = orc.handle("I want to learn DSA")
    print(f"Reply:\n{reply[:250]}...\nProvider: {used}")
    assert "DSA" in reply or "take U forward" in reply or "NeetCode" in reply, "Should invoke learning_resources!"

    print("\n--- TEST 6: 'open WhatsApp and send hi to Sukhwinder Singh' ---")
    # We test the parser routing
    m_planned = orc.planner.handle_natural_input("open WhatsApp and send hi to Sukhwinder Singh")
    assert m_planned is not None, "WhatsApp command must be recognized!"
    print("WhatsApp command recognized successfully.")

    print("\n--- TEST 7: 'open email and send a message to Rahul' (Multi-turn initiation) ---")
    reply, used = orc.handle("open email and send a message to Rahul")
    print(f"Reply:\n{reply}\nProvider: {used}")
    task = orc.task_manager.get_task()
    assert task is not None, "Task must be created!"
    assert task.task_type == "send_email", "Task type must be send_email!"
    assert task.recipient == "Rahul", f"Recipient should be Rahul, got {task.recipient}!"
    assert "account" in reply.lower(), "Should ask which email account to send from!"

    print("\n--- TEST 8: Multi-turn continuation: 'My personal Gmail' ---")
    reply, used = orc.handle("My personal Gmail")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert "message" in reply.lower() or "say" in reply.lower(), "Should ask what to say!"

    print("\n--- TEST 9: Multi-turn continuation: 'Tell him I'm sending the assignment' ---")
    reply, used = orc.handle("Tell him I'm sending the assignment")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert "attach" in reply.lower(), "Should ask about attachment!"

    print("\n--- TEST 10: Multi-turn continuation: 'Yes, attach my DSA PDF' ---")
    reply, used = orc.handle("Yes, attach my DSA PDF")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert task.stage == "SELECT_ATTACHMENT", f"Stage should be SELECT_ATTACHMENT, got {task.stage}"

    print("\n--- TEST 11: Multi-turn attachment selection: '3' ---")
    reply, used = orc.handle("3")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert task.attachment_path == r"C:\Users\User\Documents\DSA_Final.pdf", "Should attach 3rd file!"
    assert task.stage == "CONFIRM_SEND", "Should reach confirmation stage!"
    assert "Rahul" in reply and "DSA_Final.pdf" in reply, "Preview must contain recipient and attachment!"

    print("\n--- TEST 12: 'what were we doing?' ---")
    reply, used = orc.handle("what were we doing?")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert "Rahul" in reply and "send_email" in reply.lower(), "Status should describe active email task!"

    print("\n--- TEST 13: 'cancel' ---")
    reply, used = orc.handle("cancel")
    print(f"Reply:\n{reply}\nProvider: {used}")
    assert orc.task_manager.get_task() is None, "Task must be cleared after cancel!"

    print("\n=== ALL 13 TEST SUITE CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_tests()
