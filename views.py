import base64
import logging

from flask import Blueprint, render_template, Response, request, stream_with_context, url_for

from CTFd import CTFdFlask
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.plugins import register_plugin_assets_directory, register_user_page_menu_bar
from CTFd.models import Challenges

from . import scaffoldmgr, runmgr, challmgr, benchmarkmgr
from .models import AgentRun

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
    runs = AgentRun.query.order_by(AgentRun.creation_time.desc()).all()

    return render_template('llmpentestbench/admin/config.html', scaffolds=scaffolds, runs=runs)

@blueprint.route('/admin/llmpentestbench/create_benchmark', methods=["GET", "POST"])
@admins_only
def view_create_benchmark():
    if request.method == "GET":
        scaffolds = scaffoldmgr.get_scaffolds()
        challenges = Challenges.query.all()

        return render_template('llmpentestbench/admin/create_benchmark.html', scaffolds=scaffolds, challenges=challenges)
    elif request.method == "POST":
        data = request.get_json() or {}
        scaffold_ids = data.get("scaffolds")
        challenge_ids = data.get("challenges")
        display_name = data.get("display_name")
        attempts = data.get("attempts")
        stop_after_first_success = data.get("stop_after_first_success")
        time_limit = data.get("time_limit")

        if not scaffold_ids or not isinstance(scaffold_ids, list) or not all(isinstance(sid, str) for sid in scaffold_ids):
            return {"success": False, "error": "Invalid scaffold IDs"}, 400

        if not challenge_ids or not isinstance(challenge_ids, list) or not all(isinstance(cid, int) for cid in challenge_ids):
            return {"success": False, "error": "Invalid challenge IDs"}, 400

        if not display_name or not isinstance(display_name, str) or len(display_name) == 0:
            return {"success": False, "error": "Invalid display name"}, 400
        if len(display_name) > 128:
            return {"success": False, "error": "Display name is too long"}, 400

        if not isinstance(attempts, int) or attempts < 1:
            return {"success": False, "error": "Invalid amount of attempts"}, 400

        if not isinstance(stop_after_first_success, bool):
            return {"success": False, "error": "Invalid stop after first success value"}, 400

        if not isinstance(time_limit, int) or time_limit < 1:
            return {"success": False, "error": "Invalid time limit"}, 400
        
        scaffolds = [scaffoldmgr.get_scaffold(sid) for sid in scaffold_ids]
        challenges = Challenges.query.filter(Challenges.id.in_(challenge_ids)).all()
        if len(challenges) != len(challenge_ids):
            return {"success": False, "error": "One or more challenge IDs do not exist"}, 400

        logger.info(f"Received benchmark creation request (scaffolds={scaffold_ids}, challenges={challenge_ids}, attempts={attempts}, stop_after_first_success={stop_after_first_success}, time_limit={time_limit})")

        benchmarkmgr.create_benchmark(display_name, scaffolds, challenges, attempts, stop_after_first_success, time_limit)

        return {"success": True}

@blueprint.route('/admin/llmpentestbench/run/<run_id>')
@admins_only
def view_run(run_id):
    run = AgentRun.query.filter_by(id=run_id).first_or_404()
    files = [
        {
            "path": f.path,
            "url": url_for("views.files", path=f.location)
        }
        for f in run.files
    ]

    return render_template('llmpentestbench/admin/run.html', run=run, files=files)

@blueprint.route('/api/v1/plugins/llmpentestbench/run/<run_id>/stop', methods=["POST"])
@admins_only
def stop_run(run_id):
    run = AgentRun.query.filter_by(id=run_id).first_or_404()

    try:
        runmgr.user_stop_run(run)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error stopping run {run_id}", exc_info=e)
        return {"success": False, "error": str(e)}, 400

@blueprint.route('/api/v1/plugins/llmpentestbench/scaffold/<scaffold_id>/run_challenge', methods=["POST"])
@admins_only
def run_challenge(scaffold_id):
    scaffold = scaffoldmgr.get_scaffold(scaffold_id)
    if not scaffold:
        return {"success": False, "error": "Invalid scaffold_id"}, 400
    
    challenge_id = "1"  # TODO: Replace with actual challenge selection logic
    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if not challenge:
        return {"success": False, "error": f"Challenge with id {challenge_id} does not exist"}, 400

    try:
        challmgr.validate_challenge(challenge)

        runmgr.start_run(scaffold, challenge)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error starting run for scaffold {scaffold_id}", exc_info=e)
        return {"success": False, "error": str(e)}, 400

@blueprint.route('/api/v1/plugins/llmpentestbench/run/<run_id>/log_stream', methods=["GET"])
@admins_only
def get_logs_stream(run_id):
    run = AgentRun.query.filter_by(id=run_id).first_or_404()

    @stream_with_context
    def gen():
        with open(f"{run.get_folder()}/output.log", "rb") as log_file:
            while True:
                # TODO look into better file wathcing (watchdog, inotify) or select(ors)
                # TODO also stop when run is finished
                # TODO fix issue with stream being closed, likely caused by sleep statement, introduce keep-alive msgs to fix
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