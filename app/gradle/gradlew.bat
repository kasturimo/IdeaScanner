@ECHO OFF
SET DIR=%~dp0
SET GRADLE_WRAPPER_JAR=%DIR%gradle\wrapper\gradle-wrapper.jar

IF NOT EXIST "%GRADLE_WRAPPER_JAR%" (
    ECHO gradle-wrapper.jar not found. Please run "gradle wrapper" to generate it.
    EXIT /B 1
)

java -Xmx64m -cp "%GRADLE_WRAPPER_JAR%" org.gradle.wrapper.GradleWrapperMain %*
