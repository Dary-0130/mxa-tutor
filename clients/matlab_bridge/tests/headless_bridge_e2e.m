function headless_bridge_e2e(mltbxPath, baseUrl)
%HEADLESS_BRIDGE_E2E Install the toolbox and exercise the real bridge endpoint.

baseUrlText = string(baseUrl);
healthOptions = weboptions("Timeout", 5);
try
    webread(char(baseUrlText + "/health"), healthOptions);
catch ME
    error("mxa:bridge:E2EHealthFailed", "FastAPI health probe failed: %s", ME.identifier);
end

toolbox = matlab.addons.toolbox.installToolbox(mltbxPath);
cleanup = onCleanup(@() cleanupToolbox(toolbox));

assert(strcmp(readToolboxValue(toolbox, "Name"), "mxa-matlab-bridge"));
assert(strcmp(readToolboxValue(toolbox, "Version"), "0.1.0"));
assert(strcmp(readToolboxValue(toolbox, "Guid"), "2690af3d-9cfe-4442-900e-c86af37a6244"));

app = mxaMatlabBridgeApp( ...
    BaseUrl=baseUrlText, ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true);
appCleanup = onCleanup(@() delete(app));
app.setErrorText("Error in C:\Users\alice\secret\model.m at line 1");
submitted = app.submitManualError();
if ~submitted
    error("mxa:bridge:E2ESubmitFailed", "submit failed: %s", app.LastErrorIdentifier);
end
responseText = strjoin(string(app.ResponseTextArea.Value), newline);
assert(contains(responseText, "连接成功"));
assert(~contains(app.LastSanitizedText, "C:\Users\alice"));
delete(appCleanup);

cancelApp = mxaMatlabBridgeApp( ...
    BaseUrl=baseUrlText, ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) false);
cancelCleanup = onCleanup(@() delete(cancelApp));
cancelApp.setErrorText("Error in /home/alice/private/model.m");
cancelSubmitted = cancelApp.submitManualError();
assert(~cancelSubmitted);
assert(isempty(cancelApp.LastReceipt));
delete(cancelCleanup);

cleanupToolbox(toolbox);
delete(cleanup);
assert(isempty(which("mxaMatlabBridgeApp")));
end

function cleanupToolbox(toolbox)
guid = readToolboxValue(toolbox, "Guid");
installed = matlab.addons.toolbox.installedToolboxes;
if any(arrayfun(@(item) strcmp(readToolboxValue(item, "Guid"), guid), installed))
    matlab.addons.toolbox.uninstallToolbox(toolbox);
end
end

function value = readToolboxValue(toolbox, name)
if isstruct(toolbox)
    value = string(toolbox.(name));
else
    value = string(toolbox.(name));
end
end
