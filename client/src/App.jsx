import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import Questionnaire from './pages/Questionnaire.jsx';
import CoursesList from "./pages/CoursesList.jsx";

function App() {
  return (
    <Router>
      <nav style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px' }}>
        <img src="/logo.svg" alt="Site logo" style={{ height: '28px' }} />
        <Link to="/courses">Courses</Link> | <Link to="/questionnaire">Questionnaire</Link>
      </nav>
      <Routes>
        <Route path="/courses" element={<CoursesList />} />
        <Route path="/questionnaire" element={<Questionnaire />} />
      </Routes>
    </Router>
  );
}

export default App;
