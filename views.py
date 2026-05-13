import base64
import logging

from flask import Blueprint, render_template, request, Response, stream_with_context

from CTFd import CTFdFlask
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.plugins import register_plugin_assets_directory, register_user_page_menu_bar

from . import scaffoldmgr

logger = logging.getLogger("llmpentestbench.views")

blueprint = Blueprint(
    "llmpentestbench",
    __name__,
    template_folder="templates",
    static_folder="assets",
    static_url_path="/plugins/llmpentestbench/assets",
)


@blueprint.route('/admin/llmpentestbench')
@admins_only
def view_config():
    scaffolds = scaffoldmgr.get_scaffolds()

    return render_template('llmpentestbench/admin/config.html', scaffolds=scaffolds)

@blueprint.route('/admin/llmpentestbench/run/<scaffold_id>')
@admins_only
def view_run(scaffold_id):
    return render_template('llmpentestbench/admin/run.html', scaffold_id=scaffold_id)

@blueprint.route('/api/v1/plugins/llmpentestbench/scaffold/<scaffold_id>/run_challenge', methods=["POST"])
@admins_only
def run_challenge(scaffold_id):
    if not scaffold_id:
        return {"success": False, "error": "Missing scaffold_id"}, 400
    
    scaffold = scaffoldmgr.get_scaffold(scaffold_id)
    if not scaffold:
        return {"success": False, "error": "Invalid scaffold_id"}, 400

    try:
        scaffold.run_challenge()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}, 400

@blueprint.route('/api/v1/plugins/llmpentestbench/scaffold/<scaffold_id>/log_stream', methods=["GET"])
@admins_only
def get_logs_stream(scaffold_id):
    @stream_with_context
    def gen():
        with open(f"/tmp/{scaffold_id}_container.log", "rb") as log_file:
            while True:
                # TODO look into better file wathcing (watchdog, inotify) or select(ors)
                data = log_file.read(2048)
                data_encoded = base64.b64encode(data).decode('utf-8')
                if data:
                    yield f"event: log_update\ndata: {data_encoded}\n\n"
                else:
                    from time import sleep
                    sleep(0.1)

    return Response(gen(), mimetype="text/event-stream")

@authed_only
@blueprint.route('/llmpentestbench')
def view_llmpentestbench():
    return render_template('llmpentestbench/user/view.html')

def load(app: CTFdFlask):
    app.register_blueprint(blueprint)
    register_plugin_assets_directory(app,
                                     base_path="/plugins/llmpentestbench/assets",
                                     endpoint="plugins.llmpentestbench.assets")
    register_user_page_menu_bar("LLMPentestBench", "/llmpentestbench")