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
assert(contains(responseText, "连接回执已收到"));
assert(contains(responseText, "报错解释已生成"));
assert(~contains(responseText, "不提供报错解释"));
assert(~contains(app.LastSanitizedText, "C:\Users\alice"));
delete(appCleanup);

autoApp = mxaMatlabBridgeApp( ...
    BaseUrl=baseUrlText, ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true);
autoCleanup = onCleanup(@() delete(autoApp));
autoSubmitted = autoApp.runAndExplain(@throwAutoCaptureError);
if ~autoSubmitted
    error("mxa:bridge:E2EAutoSubmitFailed", "auto submit failed: %s", autoApp.LastErrorIdentifier);
end
autoResponseText = strjoin(string(autoApp.ResponseTextArea.Value), newline);
assert(contains(autoResponseText, "报错解释已生成"));
assert(isempty(autoApp.LastReceipt));
assert(~contains(autoApp.LastSanitizedText, "C:\Users\alice"));
assert(~contains(autoApp.LastSanitizedText, "sk-"));
assert(contains(autoApp.LastSanitizedText, "Undefined function or variable Kp_ctrl"));
delete(autoCleanup);

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

autoCancelApp = mxaMatlabBridgeApp( ...
    BaseUrl=baseUrlText, ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) false);
autoCancelCleanup = onCleanup(@() delete(autoCancelApp));
autoCancelSubmitted = autoCancelApp.runAndExplain(@throwAutoCaptureError);
assert(~autoCancelSubmitted);
assert(isempty(autoCancelApp.LastReceipt));
assert(isempty(autoCancelApp.LastExplanation));
delete(autoCancelCleanup);

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

function throwAutoCaptureError()
error( ...
    "mxa:bridge:E2EAutoError", ...
    "Undefined function or variable Kp_ctrl in %s token=sk-SECRET1234567890", ...
    "C:\Users\alice\secret\model.m");
end
