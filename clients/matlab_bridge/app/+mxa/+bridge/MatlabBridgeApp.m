classdef MatlabBridgeApp < handle
    %MATLABBRIDGEAPP Programmatic UI for the TASK-510 diagnostic bridge.

    properties (Constant)
        DefaultBaseUrl = "http://localhost:8000"
        ProtocolVersion = "0.3-a"
        DiagnosticKind = "manual_error"
        ClientVersion = "0.1.0"
        SafetyPrompt = "请勿粘贴源码、账号、密钥或其他敏感信息"
        NetworkErrorMessage = "连接失败,请稍后重试。"
    end

    properties
        BaseUrl (1,1) string = mxa.bridge.MatlabBridgeApp.DefaultBaseUrl
        ConfirmFunction function_handle = @mxa.bridge.defaultConfirm
        TimeoutSeconds (1,1) double = 10
        UIFigure
        InputTextArea
        PreviewTextArea
        ResponseTextArea
        SubmitButton
        StatusLabel
        LastReceipt = []
        LastSanitizedText (1,1) string = ""
        LastErrorIdentifier (1,1) string = ""
    end

    methods
        function obj = MatlabBridgeApp(options)
            arguments
                options.BaseUrl (1,1) string = mxa.bridge.MatlabBridgeApp.DefaultBaseUrl
                options.ConfirmFunction function_handle = @mxa.bridge.defaultConfirm
                options.Visible (1,1) string {mustBeMember(options.Visible, ["on", "off"])} = "on"
                options.TimeoutSeconds (1,1) double {mustBePositive} = 10
            end

            mxa.bridge.validateBaseUrl(options.BaseUrl);
            obj.BaseUrl = options.BaseUrl;
            obj.ConfirmFunction = options.ConfirmFunction;
            obj.TimeoutSeconds = options.TimeoutSeconds;
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

            payload = obj.buildPayload(snapshot);
            try
                receipt = mxa.bridge.postDiagnostic(obj.BaseUrl, payload, obj.TimeoutSeconds);
            catch ME
                obj.LastErrorIdentifier = string(ME.identifier);
                obj.setStatus(obj.NetworkErrorMessage);
                obj.ResponseTextArea.Value = cellstr(obj.NetworkErrorMessage);
                return
            end

            obj.LastReceipt = receipt;
            obj.ResponseTextArea.Value = cellstr(splitlines(mxa.bridge.formatReceipt(receipt)));
            obj.setStatus("连接成功。");
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
                "Text", "连接回执", ...
                "Position", [24 95 240 22]);
            obj.ResponseTextArea = uitextarea(obj.UIFigure, ...
                "Position", [24 24 672 70], ...
                "Editable", "off", ...
                "Value", {""});
        end

        function text = currentInputText(obj)
            text = strjoin(string(obj.InputTextArea.Value), newline);
        end

        function payload = buildPayload(obj, sanitizedText)
            payload = struct();
            payload.protocol_version = char(obj.ProtocolVersion);
            payload.request_id = char(java.util.UUID.randomUUID);
            payload.diagnostic_kind = char(obj.DiagnosticKind);
            payload.matlab_release = char("R" + string(version("-release")));
            payload.client_version = char(obj.ClientVersion);
            payload.error_text = char(sanitizedText);
            payload.consent_confirmed = true;
        end

        function setStatus(obj, text)
            obj.StatusLabel.Text = char(text);
        end
    end
end
