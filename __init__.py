from flask import Blueprint, render_template

from CTFd import CTFdFlask

plugin_blueprint = Blueprint(
    "masterthesis",
    __name__,
    template_folder="templates",
    static_folder="assets",
    static_url_path="/plugins/masterthesis/assets",
)

def load(app: CTFdFlask):
    app.register_blueprint(plugin_blueprint)
    
    @app.route('/admin/masterthesis', methods=['GET'])
    def view_config():
        return render_template('admin_view.html')
