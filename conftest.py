"""Repo-root pytest hooks."""


def pytest_sessionfinish(session, exitstatus):
    from pg_session import pg_test_mode_enabled, stop_session

    if pg_test_mode_enabled():
        stop_session()
