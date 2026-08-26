plugins {
    java
    id("org.springframework.boot") version "3.4.1"
    id("io.spring.dependency-management") version "1.1.7"
}

group = "com.example"
version = "0.1.0"
java { toolchain { languageVersion.set(JavaLanguageVersion.of(21)) } }

repositories { mavenCentral() }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("com.fasterxml.jackson.core:jackson-databind")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}

tasks.test { useJUnitPlatform() }

val assetLock = file("config/hf-assets.lock.json")

tasks.register<Exec>("updateHfAssetLock") {
    group = "verification"
    description = "Regenerate Hugging Face asset lock from local mirror and transcript policy"
    workingDir = projectDir
    commandLine("bash", "kit/r7.sh")
    inputs.file("docs/release-council-transcript.md")
    inputs.dir(provider { System.getenv("HF_MIRROR_ROOT") ?: "/data/hf-mirror" })
    inputs.dir("gradle/dependency-locks")
    outputs.file(assetLock)
}

tasks.register<Exec>("validateHfAssetLock") {
    group = "verification"
    description = "Validate asset lock against mirror, transcript, and Gradle locks"
    workingDir = projectDir
    commandLine("bash", "kit/v3.sh", assetLock.absolutePath)
    inputs.file(assetLock)
    inputs.file("docs/release-council-transcript.md")
    inputs.dir(provider { System.getenv("HF_MIRROR_ROOT") ?: "/data/hf-mirror" })
    inputs.dir("gradle/dependency-locks")
}

tasks.named("check") { dependsOn("test") }
tasks.named("bootRun") { dependsOn("test") }
