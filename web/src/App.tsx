import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ChatPage } from "./routes/ChatPage";
import { NotFoundPage } from "./routes/NotFoundPage";
import { OverviewPage } from "./routes/OverviewPage";
import { PaperResultPage } from "./routes/PaperResultPage";
import { PaperUploadPage } from "./routes/PaperUploadPage";
import { UploadPage } from "./routes/UploadPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<UploadPage />} />
          <Route path="paper" element={<PaperUploadPage />} />
          <Route path="paper/:paperId" element={<PaperResultPage />} />
          <Route path="view/:projectId" element={<OverviewPage />} />
          <Route path="view/:projectId/chat" element={<ChatPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
