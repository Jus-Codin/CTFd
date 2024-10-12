import argparse
import json
import traceback

from CTFd import create_app

parser = argparse.ArgumentParser()
parser.add_argument(
    "--export-path",
    help="Directory to export the swagger.json and openapi.json to",
    default=".",
)
args = parser.parse_args()

app = create_app()
with app.app_context(), app.test_request_context():
    try:
        from CTFd.api import CTFd_API_v1

        swagger = CTFd_API_v1.__schema__
        with open(args.export_path + "/swagger.json", "w") as f:
            json.dump(swagger, f, indent=2)

        print(f"Exported swagger.json to {args.export_path}/swagger.json")
    except Exception:
        print("Failed to export swagger json")

        traceback.print_exc()

        swagger = None

    if swagger is not None:
        # Use converter.swagger.io to convert swagger.json to openapi.json
        try:
            import requests
        except ImportError:
            print(
                "Failed to import requests, unable to convert swagger.json to openapi.json"
            )
            requests = None

        if requests is not None:
            try:
                response = requests.post(
                    "https://converter.swagger.io/api/convert", json=swagger
                )

                if response.status_code == 200:
                    with open(args.export_path + "/openapi.json", "w") as f:
                        json.dump(response.json(), f, indent=2)

                    print(f"Exported openapi.json to {args.export_path}/openapi.json")
            except Exception:
                print("Failed to export openapi json")
