from langgraph.checkpoint.memory import InMemorySaver

from onboardai.storage import EmployeeMemory
from onboardai.workflow import build_preference_memory_workflow


def test_store_fact_survives_real_thread_change():
    memory = EmployeeMemory()
    workflow = build_preference_memory_workflow(
        memory,
        checkpointer=InMemorySaver(),
    )

    cfg_a = {"configurable": {"thread_id": "thread-A"}}
    cfg_b = {"configurable": {"thread_id": "thread-B"}}

    a = workflow.invoke(
        {
            "employee_id": "EMP-THREAD-PROOF",
            "preferred_language": "Arabic",
            "training_format": "online",
        },
        cfg_a,
    )
    b = workflow.invoke(
        {"employee_id": "EMP-THREAD-PROOF"},
        cfg_b,
    )

    assert a["recalled_preferences"] == b["recalled_preferences"]
