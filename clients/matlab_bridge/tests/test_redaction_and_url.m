function tests = test_redaction_and_url
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
rootDir = fileparts(fileparts(mfilename("fullpath")));
appDir = fullfile(rootDir, "app");
addpath(appDir);
testCase.TestData.PathCleanup = onCleanup(@() rmpath(appDir));
end

function testRedactsSupportedAbsolutePaths(testCase)
inputText = [
    "Error in C:\Users\alice\secret\model.m"
    "UNC \\server\share\private\file.m"
    "POSIX /home/alice/project/file.m"
    "URI file:///C:/Users/alice/private/file.m"
];

sanitized = mxa.bridge.redactDiagnosticText(strjoin(inputText, newline));

verifyFalse(testCase, contains(sanitized, "C:\Users\alice"));
verifyFalse(testCase, contains(sanitized, "\\server\share"));
verifyFalse(testCase, contains(sanitized, "/home/alice"));
verifyFalse(testCase, contains(sanitized, "file:///C:/Users"));
verifyGreaterThanOrEqual(testCase, count(sanitized, "[REDACTED_PATH]"), 4);
end

function testRedactsSecretsAndSourceSentinels(testCase)
inputText = [
    "api_key=SECRET123456789"
    "token=sk-abcdef1234567890"
    "function y = leakSecret(x)"
];

sanitized = mxa.bridge.redactDiagnosticText(strjoin(inputText, newline));

verifyFalse(testCase, contains(sanitized, "SECRET123456789"));
verifyFalse(testCase, contains(sanitized, "sk-abcdef1234567890"));
verifyFalse(testCase, contains(sanitized, "function y"));
verifyTrue(testCase, contains(sanitized, "[REDACTED_SECRET]"));
verifyTrue(testCase, contains(sanitized, "[REDACTED_SOURCE]"));
end

function testValidateBaseUrlAllowsLocalhostHttp(testCase)
verifyWarningFree(testCase, @() mxa.bridge.validateBaseUrl("http://localhost:8000"));
end

function testValidateBaseUrlAllowsHttps(testCase)
verifyWarningFree(testCase, @() mxa.bridge.validateBaseUrl("https://example.com"));
end

function testValidateBaseUrlRejectsRemoteHttp(testCase)
verifyError( ...
    testCase, ...
    @() mxa.bridge.validateBaseUrl("http://127.0.0.1:8000"), ...
    "mxa:bridge:InvalidBaseUrl");
end

function testValidateBaseUrlRejectsUserInfo(testCase)
verifyError( ...
    testCase, ...
    @() mxa.bridge.validateBaseUrl("https://user:secret@example.com"), ...
    "mxa:bridge:InvalidBaseUrl");
end

function testDefaultTokenProviderFailsClosed(testCase)
verifyError( ...
    testCase, ...
    @() mxa.bridge.defaultTokenProvider("user-alpha", "project-alpha", ...
        "11111111-1111-4111-8111-111111111111"), ...
    "mxa:bridge:TokenProviderMissing");
end

function testCancelDoesNotSend(testCase)
diagnosticCalls = 0;
explanationCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) false, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error in C:\Users\alice\secret\model.m");
submitted = app.submitManualError();

verifyFalse(testCase, submitted);
verifyEmpty(testCase, app.LastReceipt);
verifyEqual(testCase, diagnosticCalls, 0);
verifyEqual(testCase, explanationCalls, 0);
verifyFalse(testCase, contains(app.LastSanitizedText, "C:\Users\alice"));

    function receipt = fakeDiagnosticPost(~, ~, ~)
        diagnosticCalls = diagnosticCalls + 1;
        receipt = struct();
    end

    function explanation = fakeExplanationPost(~, ~, ~)
        explanationCalls = explanationCalls + 1;
        explanation = struct();
    end
end

function testCaptureExceptionSnapshotUsesWhitelistAndRedactsUntrustedMessage(testCase)
try
    localThrowingFunction("C:\Users\alice\secret\model.m", "api_key=SECRET123456789");
catch ME
    reportText = getReport(ME, "extended", "hyperlinks", "off");
    snapshot = mxa.bridge.captureExceptionSnapshot(ME);
end

verifyTrue(testCase, contains(snapshot, "identifier: mxa:test:AutoCapture"));
verifyTrue(testCase, contains(snapshot, "message:"));
verifyTrue(testCase, contains(snapshot, "stack:"));
verifyTrue(testCase, contains(snapshot, "name: localThrowingFunction"));
verifyFalse(testCase, contains(snapshot, "C:\Users\alice"));
verifyFalse(testCase, contains(snapshot, "SECRET123456789"));
verifyFalse(testCase, contains(snapshot, mfilename("fullpath")));
verifyFalse(testCase, contains(snapshot, reportText));
verifyTrue(testCase, contains(snapshot, "[REDACTED_PATH]"));
verifyTrue(testCase, contains(snapshot, "[REDACTED_SECRET]"));
end

function testAutoCaptureTruncatesWithMarker(testCase)
longStack = repmat(struct("name", repmat("stackFrame", 1, 40), "line", 42), 1, 8);
causeItems = cell(1, 3);
for index = 1:3
    causeItems{index} = struct( ...
        "identifier", "mxa:test:Cause" + string(index), ...
        "message", repmat("causeMessage", 1, 120), ...
        "stack", longStack, ...
        "cause", []);
end
fakeException = struct( ...
    "identifier", "mxa:test:Long", ...
    "message", repmat("topMessage", 1, 400), ...
    "stack", longStack, ...
    "cause", {causeItems});

snapshot = mxa.bridge.captureExceptionSnapshot(fakeException);

verifyLessThanOrEqual(testCase, strlength(snapshot), 4096);
verifyTrue(testCase, endsWith(snapshot, "[TRUNCATED_AUTO_CAPTURE]"));
end

function testSubmitAutoCapturedErrorSendsFrozenSnapshotOnlyAfterConfirm(testCase)
confirmSnapshot = "";
payloadSnapshot = "";
diagnosticCalls = 0;
explanationCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@confirmAndMutate, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

try
    localThrowingFunction("C:\Users\alice\secret\model.m", "password=SECRET123456789");
catch ME
    submitted = app.submitAutoCapturedError(ME);
end

verifyTrue(testCase, submitted);
verifyEqual(testCase, diagnosticCalls, 0);
verifyEqual(testCase, explanationCalls, 1);
verifyEqual(testCase, payloadSnapshot, confirmSnapshot);
verifyEqual(testCase, app.LastConfirmedSnapshot, confirmSnapshot);
verifyEqual(testCase, string(app.LastExplanation.status), "completed");
verifyEqual(testCase, string(app.LastExplanation.mode), "llm_error_explanation");
verifyFalse(testCase, contains(payloadSnapshot, "C:\Users\alice"));
verifyFalse(testCase, contains(payloadSnapshot, "SECRET123456789"));

    function confirmed = confirmAndMutate(~, snapshot)
        confirmSnapshot = string(snapshot);
        assignin("base", "mxa_bridge_mutation_after_confirm", "changed");
        confirmed = true;
    end

    function receipt = fakeDiagnosticPost(~, ~, ~)
        diagnosticCalls = diagnosticCalls + 1;
        receipt = struct();
    end

    function explanation = fakeExplanationPost(~, payload, timeoutSeconds)
        explanationCalls = explanationCalls + 1;
        payloadSnapshot = string(payload.error_text);
        verifyEqual(testCase, timeoutSeconds, 60);
        verifyEqual(testCase, string(payload.diagnostic_kind), "auto_captured_error");
        explanation = makeExplanation(payload.request_id, "自动采集的报错文本");
    end
end

function testSubmitAutoCapturedErrorCancelDoesNotSend(testCase)
diagnosticCalls = 0;
explanationCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) false, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

try
    localThrowingFunction("/home/alice/private/model.m", "token=sk-abcdef1234567890");
catch ME
    submitted = app.submitAutoCapturedError(ME);
end

verifyFalse(testCase, submitted);
verifyEqual(testCase, diagnosticCalls, 0);
verifyEqual(testCase, explanationCalls, 0);
verifyEmpty(testCase, app.LastExplanation);
verifyEqual(testCase, app.LastConfirmedSnapshot, "");
verifyFalse(testCase, contains(app.LastSanitizedText, "/home/alice"));
verifyFalse(testCase, contains(app.LastSanitizedText, "sk-abcdef1234567890"));

    function receipt = fakeDiagnosticPost(~, ~, ~)
        diagnosticCalls = diagnosticCalls + 1;
        receipt = struct();
    end

    function explanation = fakeExplanationPost(~, ~, ~)
        explanationCalls = explanationCalls + 1;
        explanation = struct();
    end
end

function testRunAndExplainCapturesThrownMException(testCase)
explanationPayload = [];
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

submitted = app.runAndExplain(@() localThrowingFunction("C:\Users\alice\secret\model.m", "secret=SECRET123456789"));

verifyTrue(testCase, submitted);
verifyEqual(testCase, string(explanationPayload.diagnostic_kind), "auto_captured_error");
verifyFalse(testCase, contains(string(explanationPayload.error_text), "C:\Users\alice"));
verifyFalse(testCase, contains(string(explanationPayload.error_text), "SECRET123456789"));

    function explanation = fakeExplanationPost(~, payload, ~)
        explanationPayload = payload;
        explanation = makeExplanation(payload.request_id, "自动采集的报错文本");
    end
end

function testDiagnosticPathsUseNonPersistentConfirmContext(testCase)
contexts = strings(0, 1);
diagnosticCalls = 0;
explanationCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@fakeConfirm, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
manualSubmitted = app.submitManualError();
autoSubmitted = app.runAndExplain(@() localThrowingFunction("C:\Users\alice\model.m", "secret=SECRET123456789"));

verifyTrue(testCase, manualSubmitted);
verifyTrue(testCase, autoSubmitted);
verifyEqual(testCase, contexts, ["diagnostic"; "diagnostic"]);
verifyEqual(testCase, diagnosticCalls, 1);
verifyEqual(testCase, explanationCalls, 2);

    function confirmed = fakeConfirm(~, ~, context)
        contexts(end + 1, 1) = string(context); %#ok<AGROW>
        confirmed = true;
    end

    function receipt = fakeDiagnosticPost(~, payload, ~)
        diagnosticCalls = diagnosticCalls + 1;
        receipt = struct( ...
            "request_id", payload.request_id, ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, payload, ~)
        explanationCalls = explanationCalls + 1;
        explanation = makeExplanation(payload.request_id, "报错文本");
    end
end

function testFormatReceiptIgnoresServerMessage(testCase)
receipt = struct( ...
    "request_id", "2690af3d-9cfe-4442-900e-c86af37a6244", ...
    "status", "received", ...
    "mode", "connectivity_stub", ...
    "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");

text = mxa.bridge.formatReceipt(receipt);

verifyTrue(testCase, contains(text, "连接回执已收到"));
verifyTrue(testCase, contains(text, "status: received"));
verifyTrue(testCase, contains(text, "mode: connectivity_stub"));
verifyFalse(testCase, contains(text, "不提供报错解释"));
end

function testFormatExplanationRendersContractFields(testCase)
explanation = makeExplanation("2690af3d-9cfe-4442-900e-c86af37a6244");

text = mxa.bridge.formatExplanation(explanation);

verifyTrue(testCase, contains(text, "报错解释已生成"));
verifyTrue(testCase, contains(text, "含义:"));
verifyTrue(testCase, contains(text, "可能原因:"));
verifyTrue(testCase, contains(text, "下一步:"));
verifyTrue(testCase, contains(text, "提示:"));
verifyTrue(testCase, contains(text, "mode: llm_error_explanation"));
end

function testSubmitSendsExplanationAfterValidatedAck(testCase)
diagnosticPayload = [];
explanationPayload = [];

app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
submitted = app.submitManualError();
responseText = strjoin(string(app.ResponseTextArea.Value), newline);

verifyTrue(testCase, submitted);
verifyNotEmpty(testCase, app.LastReceipt);
verifyNotEmpty(testCase, app.LastExplanation);
verifyEqual(testCase, string(diagnosticPayload.protocol_version), "0.3-a");
verifyEqual(testCase, string(explanationPayload.protocol_version), "0.3-b1");
verifyEqual(testCase, string(explanationPayload.request_id), string(diagnosticPayload.request_id));
verifyTrue(testCase, isfield(explanationPayload, "llm_processing_consent_confirmed"));
verifyTrue(testCase, contains(responseText, "连接回执已收到"));
verifyTrue(testCase, contains(responseText, "报错解释已生成"));
verifyFalse(testCase, contains(responseText, "不提供报错解释"));

    function receipt = fakeDiagnosticPost(~, payload, timeoutSeconds)
        diagnosticPayload = payload;
        verifyEqual(testCase, timeoutSeconds, 10);
        receipt = struct( ...
            "request_id", payload.request_id, ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, payload, timeoutSeconds)
        explanationPayload = payload;
        verifyEqual(testCase, timeoutSeconds, 60);
        explanation = makeExplanation(payload.request_id, "粘贴的报错文本");
    end
end

function testExplanationFailureKeepsNeutralAck(testCase)
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
submitted = app.submitManualError();
responseText = strjoin(string(app.ResponseTextArea.Value), newline);

verifyTrue(testCase, submitted);
verifyNotEmpty(testCase, app.LastReceipt);
verifyEmpty(testCase, app.LastExplanation);
verifyTrue(testCase, contains(responseText, "连接回执已收到"));
verifyTrue(testCase, contains(responseText, "解释失败"));
verifyFalse(testCase, contains(responseText, "不提供报错解释"));
verifyEqual(testCase, app.LastErrorIdentifier, "mxa:bridge:HTTP5xx");

    function receipt = fakeDiagnosticPost(~, payload, ~)
        receipt = struct( ...
            "request_id", payload.request_id, ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, ~, ~)
        explanation = [];
        error("mxa:bridge:HTTP5xx", "service unavailable");
    end
end

function testInvalidAckDoesNotSendExplanation(testCase)
explanationCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
submitted = app.submitManualError();

verifyFalse(testCase, submitted);
verifyEmpty(testCase, app.LastReceipt);
verifyEqual(testCase, explanationCalls, 0);
verifyEqual(testCase, app.LastErrorIdentifier, "mxa:bridge:InvalidReceipt");

    function receipt = fakeDiagnosticPost(~, ~, ~)
        receipt = struct( ...
            "request_id", "11111111-1111-4111-8111-111111111111", ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, ~, ~)
        explanationCalls = explanationCalls + 1;
        explanation = makeExplanation("11111111-1111-4111-8111-111111111111", "粘贴的报错文本");
    end
end

function testRunStateStringRedactionAndUnsafeControls(testCase)
sanitized = mxa.bridge.redactRunStateString( ...
    "C:\Users\a\m.slx token=SECRET12", 64, 128);

verifyFalse(testCase, contains(sanitized, "C:\Users\a"));
verifyFalse(testCase, contains(sanitized, "SECRET12"));
verifyTrue(testCase, contains(sanitized, "[REDACTED_PATH]"));
verifyTrue(testCase, contains(sanitized, "[REDACTED_SECRET]"));
verifyError( ...
    testCase, ...
    @() mxa.bridge.redactRunStateString("bad" + newline + char(0) + "text"), ...
    "mxa:bridge:RunStateUnsafeString");
end

function testRunStateSummarizeSkipsInvalidSourceSeries(testCase)
verifyEmpty(testCase, mxa.bridge.summarizeRunStateSeries( ...
    "s1", "single", 0, 1));
verifyEmpty(testCase, mxa.bridge.summarizeRunStateSeries( ...
    "s1", "duplicate", [0 0.1 0.1], [1 2 3]));
verifyEmpty(testCase, mxa.bridge.summarizeRunStateSeries( ...
    "s1", "nonuniform", [0 0.1 0.25], [1 2 3]));
verifyEmpty(testCase, mxa.bridge.summarizeRunStateSeries( ...
    "s1", "nan", [0 0.1 0.2], [1 NaN 3]));
end

function testRunStateSummarizeIdentityGolden(testCase)
series = mxa.bridge.summarizeRunStateSeries( ...
    "simout", "simout", [0 0.1 0.2 0.3], [0 1 0 -1], "seconds", "unknown", "");

verifyEqual(testCase, string(series.representation), "identity_uniform_v1");
verifyEqual(testCase, string(series.series_id), "simout");
verifyEqual(testCase, string(series.time_unit), "s");
verifyEqual(testCase, string(series.value_unit_status), "unknown");
verifyFalse(testCase, isfield(series, "value_unit"));
verifyEqual(testCase, double(series.source_point_count), 4);
verifyEqual(testCase, series.t_start, 0);
verifyEqual(testCase, series.t_step, 0.1, "AbsTol", 1e-12);
verifyEqual(testCase, series.y, [0 1 0 -1]);
end

function testRunStateSummarizeEnvelopeGolden(testCase)
time = 0:0.5:96;
data = 1:numel(time);
series = mxa.bridge.summarizeRunStateSeries( ...
    "long_series", "long", time, data, "seconds", "known", "V");

verifyEqual(testCase, string(series.representation), "min_max_envelope_uniform_v1");
verifyEqual(testCase, string(series.value_unit), "V");
verifyEqual(testCase, double(series.source_point_count), 193);
verifyEqual(testCase, series.bucket_width, 1, "AbsTol", 1e-12);
verifyEqual(testCase, numel(series.y_min), 96);
verifyEqual(testCase, numel(series.y_max), 96);
verifyEqual(testCase, series.y_min(1), 1);
verifyEqual(testCase, series.y_max(1), 2);
verifyEqual(testCase, series.y_min(96), 191);
verifyEqual(testCase, series.y_max(96), 193);
end

function testRunStateFreezeMatchesCrossLanguageGolden(testCase)
payload = makeRunStateGoldenPayload();
repoRoot = fileparts(fileparts(fileparts(fileparts(mfilename("fullpath")))));
fixturePath = fullfile(repoRoot, "tests", "fixtures", "matlab_bridge", ...
    "run_state_golden_payload.json");
expectedJson = strip(string(fileread(fixturePath)));

[frozenJson, frozenBytes] = mxa.bridge.freezeRunStatePayload(payload);

verifyEqual(testCase, frozenJson, expectedJson);
verifyEqual(testCase, frozenBytes, unicode2native(char(expectedJson), "UTF-8"));
end

function testRunStateFreezeRejectsPayloadOver28Kb(testCase)
payload = struct();
payload.protocol_version = "0.3-b4";
payload.padding = repmat("a", 1, 28 * 1024);

verifyError( ...
    testCase, ...
    @() mxa.bridge.freezeRunStatePayload(payload), ...
    "mxa:bridge:RunStatePayloadTooLarge");
end

function testRunStateFreezeRejectsNonFiniteBeforeJsonEncode(testCase)
payload = makeRunStateGoldenPayload();
payload.series{1}.y = [0 NaN];

verifyError( ...
    testCase, ...
    @() mxa.bridge.freezeRunStatePayload(payload), ...
    "mxa:bridge:RunStateNonFiniteValue");

payload = makeRunStateGoldenPayload();
payload.metrics{1}.value = Inf;
verifyError( ...
    testCase, ...
    @() mxa.bridge.freezeRunStatePayload(payload), ...
    "mxa:bridge:RunStateNonFiniteValue");
end

function testSubmitRunStateRefreshesOnceAndResendsSameFrozenPayload(testCase)
tokenCalls = 0;
postCalls = 0;
postedJson = strings(1, 2);
postedTokens = strings(1, 2);
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    TokenProviderFunction=@fakeTokenProvider, ...
    RunStatePostFunction=@fakePostRunState);
cleanup = onCleanup(@() delete(app));

submitted = app.submitRunState( ...
    Simulink.SimulationOutput, ...
    "user-alpha", ...
    "project-alpha", ...
    "11111111-1111-4111-8111-111111111111", ...
    7);

verifyTrue(testCase, submitted);
verifyEqual(testCase, tokenCalls, 2);
verifyEqual(testCase, postCalls, 2);
verifyEqual(testCase, postedJson(1), postedJson(2));
verifyEqual(testCase, postedTokens, ["token-1", "token-2"]);
verifyEqual(testCase, app.LastConfirmedSnapshot, postedJson(1));
verifyEqual(testCase, app.LastRunStateFrozenJson, postedJson(1));
verifyFalse(testCase, contains(postedJson(1), "token-1"));
verifyFalse(testCase, contains(postedJson(1), "token-2"));

firstPayload = jsondecode(char(postedJson(1)));
secondPayload = jsondecode(char(postedJson(2)));
verifyEqual(testCase, string(firstPayload.run_id), string(secondPayload.run_id));
verifyEqual(testCase, string(app.LastRunStateReceipt.run_id), string(firstPayload.run_id));

    function token = fakeTokenProvider(userId, projectId, sessionId)
        verifyEqual(testCase, string(userId), "user-alpha");
        verifyEqual(testCase, string(projectId), "project-alpha");
        verifyEqual(testCase, string(sessionId), "11111111-1111-4111-8111-111111111111");
        tokenCalls = tokenCalls + 1;
        token = "token-" + string(tokenCalls);
    end

    function receipt = fakePostRunState(~, frozenJson, timeoutSeconds, accessToken)
        postCalls = postCalls + 1;
        postedJson(postCalls) = string(frozenJson);
        postedTokens(postCalls) = string(accessToken);
        verifyEqual(testCase, timeoutSeconds, 10);
        if postCalls == 1
            error("mxa:bridge:HTTP401", "401 unauthorized");
        end
        payload = jsondecode(char(frozenJson));
        receipt = makeRunStateReceipt(payload);
    end
end

function testSubmitRunStateStopsAfterSecond401WithoutNewRunId(testCase)
tokenCalls = 0;
postCalls = 0;
postedJson = strings(1, 2);
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    TokenProviderFunction=@fakeTokenProvider, ...
    RunStatePostFunction=@fakePostRunState);
cleanup = onCleanup(@() delete(app));

submitted = app.submitRunState( ...
    Simulink.SimulationOutput, ...
    "user-alpha", ...
    "project-alpha", ...
    "11111111-1111-4111-8111-111111111111", ...
    7);

verifyFalse(testCase, submitted);
verifyEqual(testCase, tokenCalls, 2);
verifyEqual(testCase, postCalls, 2);
verifyEqual(testCase, postedJson(1), postedJson(2));
verifyEqual(testCase, app.LastRunStateFrozenJson, postedJson(1));
verifyEqual(testCase, app.LastErrorIdentifier, "mxa:bridge:HTTP401");

firstPayload = jsondecode(char(postedJson(1)));
secondPayload = jsondecode(char(postedJson(2)));
verifyEqual(testCase, string(firstPayload.run_id), string(secondPayload.run_id));

    function token = fakeTokenProvider(~, ~, ~)
        tokenCalls = tokenCalls + 1;
        token = "expired-token-" + string(tokenCalls);
    end

    function receipt = fakePostRunState(~, frozenJson, ~, ~)
        postCalls = postCalls + 1;
        postedJson(postCalls) = string(frozenJson);
        receipt = struct();
        error("mxa:bridge:HTTP401", "401 unauthorized");
    end
end

function testSubmitRunStateDoesNotRetry409Conflict(testCase)
tokenCalls = 0;
postCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    TokenProviderFunction=@fakeTokenProvider, ...
    RunStatePostFunction=@fakePostRunState);
cleanup = onCleanup(@() delete(app));

submitted = app.submitRunState( ...
    Simulink.SimulationOutput, ...
    "user-alpha", ...
    "project-alpha", ...
    "11111111-1111-4111-8111-111111111111", ...
    7);

verifyFalse(testCase, submitted);
verifyEqual(testCase, tokenCalls, 1);
verifyEqual(testCase, postCalls, 1);
verifyEqual(testCase, app.LastErrorIdentifier, "mxa:bridge:HTTP409");
verifyTrue(testCase, contains(string(app.ResponseTextArea.Value), "运行状态冲突"));

    function token = fakeTokenProvider(~, ~, ~)
        tokenCalls = tokenCalls + 1;
        token = "token";
    end

    function receipt = fakePostRunState(~, ~, ~, ~)
        postCalls = postCalls + 1;
        receipt = struct();
        error("mxa:bridge:HTTP409", "409 conflict");
    end
end

function testSubmitRunState410RequiresNewConfirmedRun(testCase)
tokenCalls = 0;
postCalls = 0;
confirmedJson = strings(1, 2);
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@fakeConfirm, ...
    TokenProviderFunction=@fakeTokenProvider, ...
    RunStatePostFunction=@fakePostRunState);
cleanup = onCleanup(@() delete(app));

firstSubmitted = app.submitRunState( ...
    Simulink.SimulationOutput, ...
    "user-alpha", ...
    "project-alpha", ...
    "11111111-1111-4111-8111-111111111111", ...
    7);
verifyFalse(testCase, firstSubmitted);
verifyTrue(testCase, contains(string(app.ResponseTextArea.Value), "新建会话"));

secondSubmitted = app.submitRunState( ...
    Simulink.SimulationOutput, ...
    "user-alpha", ...
    "project-alpha", ...
    "11111111-1111-4111-8111-111111111111", ...
    8);

verifyTrue(testCase, secondSubmitted);
verifyEqual(testCase, tokenCalls, 2);
verifyEqual(testCase, postCalls, 2);
verifyNotEqual(testCase, confirmedJson(1), confirmedJson(2));
firstPayload = jsondecode(char(confirmedJson(1)));
secondPayload = jsondecode(char(confirmedJson(2)));
verifyNotEqual(testCase, string(firstPayload.run_id), string(secondPayload.run_id));
verifyEqual(testCase, string(firstPayload.protocol_version), "0.3-b4");
verifyEqual(testCase, string(firstPayload.consent_notice_version), "run_state_persistence_v1");

    function confirmed = fakeConfirm(~, frozenJson, context)
        verifyEqual(testCase, string(context), "run_state_persistence");
        confirmedJson(postCalls + 1) = string(frozenJson);
        confirmed = true;
    end

    function token = fakeTokenProvider(~, ~, ~)
        tokenCalls = tokenCalls + 1;
        token = "token";
    end

    function receipt = fakePostRunState(~, frozenJson, ~, ~)
        postCalls = postCalls + 1;
        if postCalls == 1
            receipt = struct();
            error("mxa:bridge:HTTP410", "410 session gone");
        end
        payload = jsondecode(char(frozenJson));
        receipt = makeRunStateReceipt(payload);
    end
end

function localThrowingFunction(pathText, secretText)
error("mxa:test:AutoCapture", "Failure at %s with %s", pathText, secretText);
end

function explanation = makeExplanation(requestId, caveatSource)
if nargin < 2
    caveatSource = "粘贴的报错文本";
end
cause = struct( ...
    "cause", "Kp_ctrl 可能尚未定义或未进入当前 workspace。", ...
    "is_inference", true, ...
    "confidence", "medium", ...
    "supporting_signals", {{"Undefined function or variable Kp_ctrl"}});
step = struct("action", "先运行 which 查看名称解析,再检查初始化脚本。");
explanation = struct( ...
    "protocol_version", "0.3-b1", ...
    "request_id", requestId, ...
    "status", "completed", ...
    "mode", "llm_error_explanation", ...
    "meaning", "这段报错表示 MATLAB 没找到 Kp_ctrl 这个名称。", ...
    "likely_causes", cause, ...
    "next_steps", step, ...
    "caveats", {{"这里只基于" + caveatSource + ",没有运行仿真。"}});
end

function payload = makeRunStateGoldenPayload()
metric = struct();
metric.name = "wall_clock_elapsed";
metric.value = 1.25;
metric.unit_status = "known";
metric.unit = "s";

series = struct();
series.representation = "identity_uniform_v1";
series.series_id = "simout";
series.label = "simout";
series.time_unit = "s";
series.value_unit_status = "unknown";
series.sample_order = "chronological";
series.source_point_count = int32(4);
series.t_start = 0;
series.t_step = 0.1;
series.y = [0 1 0 -1];

payload = struct();
payload.protocol_version = "0.3-b4";
payload.request_id = "2690af3d-9cfe-4442-900e-c86af37a6244";
payload.session_id = "11111111-1111-4111-8111-111111111111";
payload.run_id = "22222222-2222-4222-8222-222222222222";
payload.run_sequence = int32(7);
payload.matlab_release = "R2026a";
payload.client_version = "0.1.0";
payload.run_state_sharing_consent_confirmed = true;
payload.consent_notice_version = "run_state_persistence_v1";
payload.run_status = "completed";
payload.convergence_status = "not_applicable";
payload.stop_reason = "ReachedStopTime";
payload.solver = "ode45";
payload.metrics_status = "available";
payload.metrics = {metric};
payload.series_status = "available";
payload.series = {series};
end

function receipt = makeRunStateReceipt(payload)
receipt = struct( ...
    "protocol_version", payload.protocol_version, ...
    "status", "persisted", ...
    "mode", "durable_persisted", ...
    "durable", true, ...
    "request_id", payload.request_id, ...
    "run_id", payload.run_id, ...
    "run_sequence", payload.run_sequence);
end
