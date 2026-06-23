function outputFile = package_mxa_matlab_bridge(options)
%PACKAGE_MXA_MATLAB_BRIDGE Build the TASK-510 MATLAB toolbox artifact.

arguments
    options.OutputDir (1,1) string = ""
end

scriptDir = fileparts(mfilename("fullpath"));
rootDir = fileparts(scriptDir);
appDir = fullfile(rootDir, "app");
if strlength(options.OutputDir) == 0
    outputDir = fullfile(rootDir, "dist");
else
    outputDir = char(options.OutputDir);
end
if ~exist(outputDir, "dir")
    mkdir(outputDir);
end

identifier = "2690af3d-9cfe-4442-900e-c86af37a6244";
toolboxOptions = matlab.addons.toolbox.ToolboxOptions(appDir, identifier);
toolboxOptions.ToolboxName = "mxa-matlab-bridge";
toolboxOptions.ToolboxVersion = "0.1.0";
toolboxOptions.Summary = "MXA Tutor MATLAB diagnostic transport bridge";
toolboxOptions.Description = "TASK-510 transport-only MATLAB Add-on bridge.";
toolboxOptions.AuthorName = "mxa-tutor";
toolboxOptions.MinimumMatlabRelease = "R2026a";
toolboxOptions.MaximumMatlabRelease = "R2026a";
toolboxOptions.SupportedPlatforms.Win64 = true;
toolboxOptions.SupportedPlatforms.Mac = false;
toolboxOptions.SupportedPlatforms.Glnxa64 = false;
toolboxOptions.SupportedPlatforms.MatlabOnline = false;
toolboxOptions.OutputFile = fullfile(outputDir, "mxa-matlab-bridge-0.1.0.mltbx");

toolboxFiles = [
    fullfile(appDir, "mxaMatlabBridgeApp.m")
    fullfile(appDir, "+mxa", "+bridge", "MatlabBridgeApp.m")
    fullfile(appDir, "+mxa", "+bridge", "captureExceptionSnapshot.m")
    fullfile(appDir, "+mxa", "+bridge", "defaultConfirm.m")
    fullfile(appDir, "+mxa", "+bridge", "formatExplanation.m")
    fullfile(appDir, "+mxa", "+bridge", "formatReceipt.m")
    fullfile(appDir, "+mxa", "+bridge", "postDiagnostic.m")
    fullfile(appDir, "+mxa", "+bridge", "postExplanation.m")
    fullfile(appDir, "+mxa", "+bridge", "redactDiagnosticText.m")
    fullfile(appDir, "+mxa", "+bridge", "validateBaseUrl.m")
];
toolboxOptions.ToolboxFiles = toolboxFiles;
toolboxOptions.ToolboxMatlabPath = appDir;
toolboxOptions.AppGalleryFiles = fullfile(appDir, "mxaMatlabBridgeApp.m");

matlab.addons.toolbox.packageToolbox(toolboxOptions);
outputFile = string(toolboxOptions.OutputFile);
end
