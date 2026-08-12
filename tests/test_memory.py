from onboardai.storage import EmployeeMemory


def test_long_term_fact_survives_a_thread_change():
    memory = EmployeeMemory()
    employee_id = "EMP-THREAD-PROOF"
    thread_a = "thread-A"
    thread_b = "thread-B"
    assert thread_a != thread_b

    memory.remember_preferences(
        employee_id,
        preferred_language="Arabic",
        training_format="online",
    )
    recalled_in_thread_b = memory.recall_preferences(employee_id)
    assert recalled_in_thread_b == {
        "preferred_language": "Arabic",
        "training_format": "online",
    }
