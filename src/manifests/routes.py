from sanic import Sanic

from manifests.generator import generate_manifests


def setup_routes(app: Sanic):
    app.add_route(generate_manifests, "/<environment_id:string>")
