import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import PacketPage from './pages/PacketPage'
import InterviewPage from './pages/InterviewPage'
import './App.css'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <a href="/" className="logo-link">
          <h1 className="title">Interview AI</h1>
          <p className="subtitle">Texas A&M — Interview-ready in minutes</p>
        </a>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/packet/:id" element={<PacketPage />} />
          <Route path="/interview/:id" element={<InterviewPage />} />
        </Routes>
      </main>

      <footer className="footer">
        <p>Data: S3, Textract, Glue, Comprehend, Kendra. Intelligence: Bedrock. Storage: DynamoDB.</p>
      </footer>
    </div>
  )
}
