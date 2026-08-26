# Aurora registry toolchain: make the JDK, Maven and the verifier's Python
# resolvable from any shell, including login shells that rebuild PATH.
export JAVA_HOME="/opt/java/openjdk"
export PATH="/opt/venv/bin:${JAVA_HOME}/bin:${PATH}"
export MAVEN_OPTS="-Dmaven.repo.local=/root/.m2/repository"
