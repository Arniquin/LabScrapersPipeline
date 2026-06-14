FROM quay.io/jupyter/base-notebook:latest

# Install system build dependencies as root
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Switch back to the safe Jupyter user
USER ${NB_UID}

# Install VS Code backend and the Jupyter proxy extensions
RUN mamba install -y -c conda-forge code-server jupyter-server-proxy jupyter-vscode-proxy && \
    mamba clean --all -f -y

# Install VS Code extensions for a better IDE experience
# We do this as the user NB_USER to ensure they are available in the persistent home if needed,
# but here they will be in the image layer.
RUN code-server --install-extension ms-python.python && \
    code-server --install-extension ms-toolsai.jupyter && \
    code-server --install-extension ms-python.black-formatter

# Set up VS Code settings
COPY --chown=${NB_UID}:${NB_GID} vscode_settings.json /home/${NB_USER}/.local/share/code-server/User/settings.json

# Install your Python requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

EXPOSE 8888