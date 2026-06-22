"""포트폴리오 API에서 GET/POST 역할이 다시 섞이지 않는지 확인한다."""

from app.main import app


def route_methods() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods:
            result[path] = set(methods)
    return result


def test_canonical_portfolio_methods() -> None:
    routes = route_methods()

    assert routes["/api/portfolio/config"] == {"GET"}
    assert routes["/api/portfolio/calculate"] == {"POST"}
    assert routes["/api/portfolio/stress-test"] == {"POST"}


def test_legacy_portfolio_routes_are_not_mounted() -> None:
    routes = route_methods()
    legacy_paths = {
        "/portfolio/calculate",
        "/portfolio/stress-test",
        "/portfolio/stress-metrics",
        "/api/portfolio/all",
        "/api/portfolio/current",
        "/api/portfolio/a",
        "/api/portfolio/b",
        "/api/portfolio/bundle",
        "/api/backtest",
        "/api/tax-inputs",
        "/assets",
        "/guidelines",
    }

    assert legacy_paths.isdisjoint(routes)
