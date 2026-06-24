classdef MatlabBridgeApp < handle
    %MATLABBRIDGEAPP Programmatic UI for the TASK-510 diagnostic bridge.

    properties (Constant)
        DefaultBaseUrl = "http://localhost:8000"
        DiagnosticProtocolVersion = "0.3-a"
        ExplanationProtocolVersion = "0.3-b1"
        RunStateProtocolVersion = "0.3-b3"
        DiagnosticKind = "manual_error"
        AutoCapturedDiagnosticKind = "auto_captured_error"
        ClientVersion = "0.1.0"
        SafetyPrompt = "请勿粘贴源码、账号、密钥或其他敏感信息"
        NetworkErrorMessage = "连接失败,请稍后重试。"
        ExplanationErrorMessage = "解释失败,请稍后重试。"
        RunStateErrorMessage = "运行状态发送失败,请稍后重试。"
    end

    properties
        BaseUrl (1,1) string = mxa.bridge.MatlabBridgeApp.DefaultBaseUrl
        ConfirmFunction function_handle = @mxa.bridge.defaultConfirm
        DiagnosticPostFunction function_handle = @mxa.bridge.postDiagnostic
        ExplanationPostFunction function_handle = @mxa.bridge.postExplanation
        RunStatePostFunction function_handle = @mxa.bridge.postRunState
        TimeoutSeconds (1,1) double = 10
        ExplanationTimeoutSeconds (1,1) double = 60
        UIFigure
        InputTextArea
        PreviewTextArea
        ResponseTextArea
        SubmitButton
        StatusLabel
        LastReceipt = []
        LastExplanation = []
        LastRunStateReceipt = []
        LastSanitizedText (1,1) string = ""
        LastConfirmedSnapshot (1,1) string = ""
        LastRunStateFrozenJson (1,1) string = ""
        LastRunStateFrozenBytes = uint8.empty(1, 0)
        LastErrorIdentifier (1,1) string = ""
    end

    methods
        function obj = MatlabBridgeApp(options)
            arguments
                options.BaseUrl (1,1) string = mxa.bridge.MatlabBridgeApp.DefaultBaseUrl
                options.ConfirmFunction function_handle = @mxa.bridge.defaultConfirm
                options.DiagnosticPostFunction function_handle = @mxa.bridge.postDiagnostic
                options.ExplanationPostFunction function_handle = @mxa.bridge.postExplanation
                options.RunStatePostFunction function_handle = @mxa.bridge.postRunState
                options.Visible (1,1) string {mustBeMember(options.Visible, ["on", "off"])} = "on"
                options.TimeoutSeconds (1,1) double {mustBePositive} = 10
                options.ExplanationTimeoutSeconds (1,1) double {mustBePositive} = 60
            end

            mxa.bridge.validateBaseUrl(options.BaseUrl);
            obj.BaseUrl = options.BaseUrl;
            obj.ConfirmFunction = options.ConfirmFunction;
            obj.DiagnosticPostFunction = options.DiagnosticPostFunction;
            obj.ExplanationPostFunction = options.ExplanationPostFunction;
            obj.RunStatePostFunction = options.RunStatePostFunction;
            obj.TimeoutSeconds = options.TimeoutSeconds;
            obj.ExplanationTimeoutSeconds = options.ExplanationTimeoutSeconds;
            obj.createComponents(options.Visible);
        end

        function delete(obj)
            if ~isempty(obj.UIFigure) && isvalid(obj.UIFigure)
                delete(obj.UIFigure);
            end
        end

        function setErrorText(obj, text)
            obj.InputTextArea.Value = cellstr(splitlines(string(text)));
            obj.updatePreview();
        end

        function sanitized = updatePreview(obj)
            rawText = obj.currentInputText();
            sanitized = mxa.bridge.redactDiagnosticText(rawText);
            obj.LastSanitizedText = sanitized;
            obj.PreviewTextArea.Value = cellstr(splitlines(sanitized));
        end

        function submitted = submitManualError(obj)
            snapshot = obj.updatePreview();
            submitted = false;
            obj.LastReceipt = [];
            obj.LastExplanation = [];
            obj.LastConfirmedSnapshot = "";
            obj.LastErrorIdentifier = "";

            if strlength(strtrim(snapshot)) == 0
                obj.setStatus("诊断内容为空。");
                obj.ResponseTextArea.Value = cellstr("诊断内容为空。");
                return
            end

            confirmed = false;
            try
                confirmed = logical(obj.ConfirmFunction(obj.UIFigure, snapshot));
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus("已取消发送。");
                obj.ResponseTextArea.Value = cellstr("已取消发送。");
                return
            end

            if ~confirmed
                obj.setStatus("已取消发送。");
                obj.ResponseTextArea.Value = cellstr("已取消发送。");
                return
            end

            obj.LastConfirmedSnapshot = snapshot;
            requestId = char(java.util.UUID.randomUUID);
            diagnosticPayload = obj.buildDiagnosticPayload(snapshot, requestId);
            try
                receipt = obj.DiagnosticPostFunction( ...
                    obj.BaseUrl, ...
                    diagnosticPayload, ...
                    obj.TimeoutSeconds);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus(obj.NetworkErrorMessage);
                obj.ResponseTextArea.Value = cellstr(obj.NetworkErrorMessage);
                return
            end

            if ~obj.isValidReceipt(receipt, requestId)
                obj.LastErrorIdentifier = "mxa:bridge:InvalidReceipt";
                obj.setStatus("连接回执校验失败。");
                obj.ResponseTextArea.Value = cellstr("连接回执校验失败。");
                return
            end

            obj.LastReceipt = receipt;
            ackText = mxa.bridge.formatReceipt(receipt);
            obj.ResponseTextArea.Value = cellstr(splitlines(ackText));
            obj.setStatus("连接成功,正在生成解释。");
            submitted = true;

            explanationPayload = obj.buildExplanationPayload(snapshot, requestId);
            try
                explanation = obj.ExplanationPostFunction( ...
                    obj.BaseUrl, ...
                    explanationPayload, ...
                    obj.ExplanationTimeoutSeconds);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus(obj.ExplanationErrorMessage);
                obj.ResponseTextArea.Value = cellstr(splitlines( ...
                    ackText + newline + obj.ExplanationErrorMessage));
                return
            end

            obj.LastExplanation = explanation;
            obj.ResponseTextArea.Value = cellstr(splitlines( ...
                ackText + newline + mxa.bridge.formatExplanation(explanation)));
            obj.setStatus("解释完成。");
        end

        function submitted = runAndExplain(obj, runnable)
            arguments
                obj
                runnable function_handle
            end

            submitted = false;
            try
                runnable();
            catch ME
                submitted = obj.submitAutoCapturedError(ME);
                return
            end

            obj.setStatus("未捕获到 MATLAB 报错。");
            obj.ResponseTextArea.Value = cellstr("未捕获到 MATLAB 报错。");
        end

        function submitted = submitAutoCapturedError(obj, caughtException)
            submitted = false;
            obj.LastReceipt = [];
            obj.LastExplanation = [];
            obj.LastSanitizedText = "";
            obj.LastConfirmedSnapshot = "";
            obj.LastErrorIdentifier = "";

            try
                snapshot = mxa.bridge.captureExceptionSnapshot(caughtException);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus("自动采集失败,未发送。");
                obj.ResponseTextArea.Value = cellstr("自动采集失败,未发送。");
                return
            end

            obj.LastSanitizedText = snapshot;
            obj.PreviewTextArea.Value = cellstr(splitlines(snapshot));
            confirmed = false;
            try
                confirmed = logical(obj.ConfirmFunction(obj.UIFigure, snapshot));
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus("已取消发送。");
                obj.ResponseTextArea.Value = cellstr("已取消发送。");
                return
            end

            if ~confirmed
                obj.setStatus("已取消发送。");
                obj.ResponseTextArea.Value = cellstr("已取消发送。");
                return
            end

            obj.LastConfirmedSnapshot = snapshot;
            requestId = char(java.util.UUID.randomUUID);
            explanationPayload = obj.buildExplanationPayload( ...
                snapshot, ...
                requestId, ...
                obj.AutoCapturedDiagnosticKind);
            try
                explanation = obj.ExplanationPostFunction( ...
                    obj.BaseUrl, ...
                    explanationPayload, ...
                    obj.ExplanationTimeoutSeconds);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus(obj.ExplanationErrorMessage);
                obj.ResponseTextArea.Value = cellstr(obj.ExplanationErrorMessage);
                return
            end

            obj.LastExplanation = explanation;
            obj.ResponseTextArea.Value = cellstr(splitlines(mxa.bridge.formatExplanation(explanation)));
            obj.setStatus("解释完成。");
            submitted = true;
        end

        function submitted = submitRunState(obj, simulationOutput, sessionId, runSequence)
            submitted = false;
            obj.LastRunStateReceipt = [];
            obj.LastRunStateFrozenJson = "";
            obj.LastRunStateFrozenBytes = uint8.empty(1, 0);
            obj.LastConfirmedSnapshot = "";
            obj.LastErrorIdentifier = "";

            requestId = char(java.util.UUID.randomUUID);
            runId = char(java.util.UUID.randomUUID);
            try
                payload = mxa.bridge.captureRunStateSnapshot( ...
                    simulationOutput, sessionId, runSequence, requestId, runId);
                [frozenJson, frozenBytes] = mxa.bridge.freezeRunStatePayload(payload);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus("运行状态采集失败,未发送。");
                obj.ResponseTextArea.Value = cellstr("运行状态采集失败,未发送。");
                return
            end

            obj.PreviewTextArea.Value = cellstr(splitlines(frozenJson));
            confirmed = false;
            try
                confirmed = logical(obj.ConfirmFunction(obj.UIFigure, frozenJson));
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus("已取消发送。");
                obj.ResponseTextArea.Value = cellstr("已取消发送。");
                return
            end

            if ~confirmed
                obj.setStatus("已取消发送。");
                obj.ResponseTextArea.Value = cellstr("已取消发送。");
                return
            end

            obj.LastConfirmedSnapshot = frozenJson;
            obj.LastRunStateFrozenJson = frozenJson;
            obj.LastRunStateFrozenBytes = frozenBytes;
            try
                receipt = obj.RunStatePostFunction( ...
                    obj.BaseUrl, frozenJson, obj.TimeoutSeconds);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus(obj.RunStateErrorMessage);
                obj.ResponseTextArea.Value = cellstr(obj.RunStateErrorMessage);
                return
            end

            if ~obj.isValidRunStateReceipt(receipt, payload)
                obj.LastErrorIdentifier = "mxa:bridge:InvalidRunStateReceipt";
                obj.setStatus("运行状态回执校验失败。");
                obj.ResponseTextArea.Value = cellstr("运行状态回执校验失败。");
                return
            end

            obj.LastRunStateReceipt = receipt;
            obj.ResponseTextArea.Value = cellstr("运行状态已校验。");
            obj.setStatus("运行状态已校验。");
            submitted = true;
        end
    end

    methods (Access = private)
        function createComponents(obj, visible)
            obj.UIFigure = uifigure( ...
                "Name", "mxa-matlab-bridge", ...
                "Position", [100 100 720 560], ...
                "Visible", visible);

            uilabel(obj.UIFigure, ...
                "Text", obj.SafetyPrompt, ...
                "Position", [24 520 672 24], ...
                "FontWeight", "bold");
            uilabel(obj.UIFigure, ...
                "Text", "手动粘贴错误文本", ...
                "Position", [24 490 240 22]);
            obj.InputTextArea = uitextarea(obj.UIFigure, ...
                "Position", [24 315 672 170], ...
                "Value", {""});
            obj.InputTextArea.ValueChangedFcn = @(~, ~) obj.updatePreview();

            uilabel(obj.UIFigure, ...
                "Text", "待发送预览", ...
                "Position", [24 285 240 22]);
            obj.PreviewTextArea = uitextarea(obj.UIFigure, ...
                "Position", [24 165 672 115], ...
                "Editable", "off", ...
                "Value", {""});

            obj.SubmitButton = uibutton(obj.UIFigure, ...
                "Text", "发送诊断", ...
                "Position", [24 125 120 30], ...
                "ButtonPushedFcn", @(~, ~) obj.submitManualError());
            obj.StatusLabel = uilabel(obj.UIFigure, ...
                "Text", "等待输入。", ...
                "Position", [160 125 536 30]);

            uilabel(obj.UIFigure, ...
                "Text", "连接回执与解释", ...
                "Position", [24 95 240 22]);
            obj.ResponseTextArea = uitextarea(obj.UIFigure, ...
                "Position", [24 24 672 70], ...
                "Editable", "off", ...
                "Value", {""});
        end

        function text = currentInputText(obj)
            text = strjoin(string(obj.InputTextArea.Value), newline);
        end

        function payload = buildDiagnosticPayload(obj, sanitizedText, requestId)
            payload = struct();
            payload.protocol_version = char(obj.DiagnosticProtocolVersion);
            payload.request_id = char(requestId);
            payload.diagnostic_kind = char(obj.DiagnosticKind);
            payload.matlab_release = char("R" + string(version("-release")));
            payload.client_version = char(obj.ClientVersion);
            payload.error_text = char(sanitizedText);
            payload.consent_confirmed = true;
        end

        function payload = buildExplanationPayload(obj, sanitizedText, requestId, diagnosticKind)
            if ~exist("diagnosticKind", "var")
                diagnosticKind = obj.DiagnosticKind;
            end
            payload = struct();
            payload.protocol_version = char(obj.ExplanationProtocolVersion);
            payload.request_id = char(requestId);
            payload.diagnostic_kind = char(diagnosticKind);
            payload.matlab_release = char("R" + string(version("-release")));
            payload.client_version = char(obj.ClientVersion);
            payload.error_text = char(sanitizedText);
            payload.llm_processing_consent_confirmed = true;
        end

        function valid = isValidReceipt(~, receipt, requestId)
            valid = false;
            if ~isstruct(receipt)
                return
            end
            requiredFields = ["request_id", "status", "mode"];
            for index = 1:numel(requiredFields)
                if ~isfield(receipt, requiredFields(index))
                    return
                end
            end
            valid = strcmp(string(receipt.request_id), string(requestId)) && ...
                strcmp(string(receipt.status), "received") && ...
                strcmp(string(receipt.mode), "connectivity_stub");
        end

        function valid = isValidRunStateReceipt(~, receipt, payload)
            valid = false;
            if ~isstruct(receipt)
                return
            end
            requiredFields = ["request_id", "run_id", "run_sequence", "status", "mode", "durable"];
            for index = 1:numel(requiredFields)
                if ~isfield(receipt, requiredFields(index))
                    return
                end
            end
            durableFalse = isequal(receipt.durable, false) || isequal(receipt.durable, 0);
            valid = strcmp(string(receipt.request_id), string(payload.request_id)) && ...
                strcmp(string(receipt.run_id), string(payload.run_id)) && ...
                double(receipt.run_sequence) == double(payload.run_sequence) && ...
                strcmp(string(receipt.status), "validated") && ...
                strcmp(string(receipt.mode), "ephemeral_validation") && ...
                durableFalse;
        end

        function setStatus(obj, text)
            obj.StatusLabel.Text = char(text);
        end
    end
end
