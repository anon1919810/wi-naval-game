"""Frozen results exported without invoking any calculators."""
import csv
import io
import json


def serialize_report(result, format="json"):
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
    if format == "json":
        return encoded + "\n"
    if format != "csv":
        raise ValueError("format must be json or csv")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["request_fingerprint", "status", "simulated_time_s", "path", "value_json"])

    def leaves(value, path=""):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                yield from leaves(child, path + "/" + str(key).replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list) and value:
            for index, child in enumerate(value):
                yield from leaves(child, path + "/" + str(index))
        else:
            yield path, value

    # JSON Pointer leaves avoid placing an entire multi-megabyte report in one
    # CSV cell. Nulls and empty containers survive the flat representation.
    for path, value in leaves(result):
        writer.writerow([result["request_fingerprint"], result["status"], result["simulated_duration_s"], path,
                         json.dumps(value, ensure_ascii=False, allow_nan=False)])
    return output.getvalue()
