from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import yaml


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def parse_import(source_type: str, content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if source_type == "openapi":
        return parse_openapi(content)
    if source_type == "postman":
        return parse_postman(content)
    if source_type == "har":
        return parse_har(content)
    if source_type == "burp":
        return parse_burp(content)
    if source_type == "graphql":
        return parse_graphql_schema(content)
    if source_type == "raw_url":
        return parse_raw_urls(content)
    return [], {"parser": "notes", "length": len(content)}


def _load_structured(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        loaded = yaml.safe_load(content)
        if not isinstance(loaded, dict):
            raise ValueError("Expected JSON/YAML object")
        return loaded


def parse_openapi(content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec = _load_structured(content)
    endpoints: list[dict[str, Any]] = []
    servers = spec.get("servers", [])
    base_urls = [s.get("url") for s in servers if isinstance(s, dict) and s.get("url")]
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in HTTP_METHODS:
                continue
            parameters = []
            if isinstance(operation, dict):
                parameters.extend(operation.get("parameters", []) or [])
                request_body = operation.get("requestBody")
            else:
                request_body = None
            endpoints.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "base_urls": base_urls,
                    "operation_id": operation.get("operationId") if isinstance(operation, dict) else None,
                    "summary": operation.get("summary") if isinstance(operation, dict) else None,
                    "parameters": parameters,
                    "request_body_present": request_body is not None,
                    "source": "openapi",
                }
            )
    return endpoints, {"title": spec.get("info", {}).get("title"), "version": spec.get("info", {}).get("version"), "parser": "openapi"}


def parse_postman(content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    collection = json.loads(content)
    endpoints: list[dict[str, Any]] = []

    def walk(items: list[dict[str, Any]], folder: str = "") -> None:
        for item in items:
            name = item.get("name", "unnamed")
            if "item" in item:
                walk(item.get("item", []), folder=f"{folder}/{name}".strip("/"))
                continue
            request = item.get("request", {})
            method = request.get("method", "GET")
            url = request.get("url", {})
            raw = url.get("raw") if isinstance(url, dict) else str(url)
            path = raw or ""
            endpoints.append({"method": method.upper(), "path": path, "name": name, "folder": folder, "source": "postman"})

    walk(collection.get("item", []))
    return endpoints, {"name": collection.get("info", {}).get("name"), "parser": "postman"}


def parse_har(content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    har = json.loads(content)
    endpoints = []
    for entry in har.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        url = request.get("url", "")
        parsed = urlparse(url)
        endpoints.append(
            {
                "method": request.get("method", "GET").upper(),
                "path": parsed.path or url,
                "host": parsed.netloc,
                "query": parsed.query,
                "status": entry.get("response", {}).get("status"),
                "mime_type": entry.get("response", {}).get("content", {}).get("mimeType"),
                "source": "har",
            }
        )
    return endpoints, {"entries": len(endpoints), "parser": "har"}


def parse_burp(content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(content)
        for item in root.findall(".//item"):
            method = (item.findtext("method") or "GET").upper()
            url = item.findtext("url") or ""
            parsed = urlparse(url)
            endpoints.append({"method": method, "path": parsed.path or url, "host": parsed.netloc, "source": "burp"})
    except ET.ParseError:
        # Fallback for simple Burp/HTTP text exports.
        for match in re.finditer(r"(?m)^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(\S+)", content):
            endpoints.append({"method": match.group(1), "path": match.group(2), "source": "burp-text"})
    return endpoints, {"entries": len(endpoints), "parser": "burp"}


def parse_graphql_schema(content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    current_type = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("type Query"):
            current_type = "Query"
            continue
        if line.startswith("type Mutation"):
            current_type = "Mutation"
            continue
        if current_type and line.startswith("}"):
            current_type = None
            continue
        if current_type and line and not line.startswith("#"):
            field = line.split("(")[0].split(":")[0].strip()
            if field:
                endpoints.append({"method": "POST", "path": "/graphql", "operation": field, "operation_type": current_type, "source": "graphql"})
    return endpoints, {"operations": len(endpoints), "parser": "graphql"}


def parse_raw_urls(content: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = urlparse(line if "://" in line else f"https://{line}")
        endpoints.append({"method": "GET", "path": parsed.path or "/", "host": parsed.netloc, "source": "raw_url"})
    return endpoints, {"entries": len(endpoints), "parser": "raw_url"}
