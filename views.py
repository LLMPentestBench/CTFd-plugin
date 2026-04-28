from flask import Blueprint, render_template, current_app

from CTFd import CTFdFlask
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.plugins import register_user_page_menu_bar

from . import scaffoldmgr

blueprint = Blueprint(
    "masterthesis",
    __name__,
    template_folder="templates",
    static_folder="assets",
    static_url_path="/plugins/masterthesis/assets",
)


@blueprint.route('/admin/masterthesis')
@admins_only
def view_config():
    scaffolds = scaffoldmgr.get_scaffolds()

    return render_template('masterthesis/admin/config.html', scaffolds=scaffolds, ScaffoldStatus=scaffoldmgr.ScaffoldStatus)

@authed_only
@blueprint.route('/masterthesis')
def view_masterthesis():
    return render_template('masterthesis/user/view.html')

def load(app: CTFdFlask):
    app.register_blueprint(blueprint)
    register_user_page_menu_bar("Master Thesis", "/masterthesis")