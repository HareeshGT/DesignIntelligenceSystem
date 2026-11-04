from app.services.memory import ProjectMemory


def test_project_memory_is_scoped_by_project(tmp_path):
    memory = ProjectMemory(str(tmp_path / "memory.db"))
    memory.append("project-a", "decision", {"theme": "adaptive"})
    memory.append("project-b", "decision", {"theme": "minimal"})
    events = memory.get_events("project-a")
    assert len(events) == 1
    assert events[0]["payload"]["theme"] == "adaptive"
