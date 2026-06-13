from pathlib import Path

from app.parsers.input_parsers import parse_import


def test_openapi_parser_extracts_endpoints():
    content = Path("examples/sample_openapi.yaml").read_text()
    endpoints, metadata = parse_import("openapi", content)
    assert metadata["parser"] == "openapi"
    assert len(endpoints) == 4
    assert any(e["path"] == "/users/{userId}" and e["method"] == "GET" for e in endpoints)


def test_graphql_parser_extracts_operations():
    content = """
    type Query {
      user(id: ID!): User
    }
    type Mutation {
      updateRole(userId: ID!, role: String!): User
    }
    """
    endpoints, metadata = parse_import("graphql", content)
    assert metadata["parser"] == "graphql"
    assert len(endpoints) == 2
