import { useState, useEffect } from 'react';

function Questionnaire() {
    const [currentStep, setCurrentStep] = useState(0);
    const [formData, setFormData] = useState({
        program: '',
        semester: '',
        major: '',
        minor: ''
    });
    const [isFinished, setIsFinished] = useState(false);

    const allQuestions = [
        {
            key: 'program',
            question: 'Which program are you in?',
            options: ['Bachelor', 'Master', 'PhD']
        },{
            key: 'semester',
            question: 'Which semester?',
            getOptions: (formData) => {
                if (formData.program === 'Bachelor') return ['BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'BA6'];
                if (formData.program === 'Master') return ['MA1', 'MA2', 'MA3', 'MA4'];
                return [];
            }
        },{
            key: 'major',
            question: 'Which major?',
            getOptions: (formData) => {
                if (formData.program === 'Bachelor') return [
                    'Architecture',
                    'Chemistry and Chemical Engineering',
                    'Civil Engineering',
                    'Communication Systems',
                    'Computer Science',
                    'Electrical and Electronics Engineering',
                    'Environmental Sciences and Engineering',
                    'Life Sciences Engineering',
                    'Materials Science and Engineering',
                    'Mathematics',
                    'Mechanical Engineering',
                    'Microengineering',
                    'Physics'
                ];
                if (formData.program === 'Master') return [
                    'Applied Mathematics',
                    'Architecture',
                    'Chemical Engineering and Biotechnology',
                    'Civil Engineering',
                    'Communication Systems',
                    'Computational science and Engineering',
                    'Computer Science',
                    'Cyber Security',
                    'Data Science',
                    'Digital Humanities',
                    'Electrical and Electronic Engineering',
                    'Energy Science and Technology',
                    'Environmental Sciences and Engineering',
                    'Financial Engineering',
                    'Life Sciences Engineering',
                    'Management, Technology and Entrepreneurship',
                    'Materials Science and Engineering',
                    'Mathematics',
                    'Mechanical Engineering',
                    'Microengineering',
                    'Molecular and Biological Chemistry',
                    'Neuro-X',
                    'Nuclear Engineering',
                    'Physics and Applied Physics',
                    'Quantum Science and Engineering',
                    'Robotics',
                    'Statistics',
                    'Sustainable Management and Technology',
                    'Urban Systems'
                ];
                if (formData.program === 'PhD') return [
                    'Advanced Manufacturing',
                    'Architecture and Sciences of the City',
                    'Biotechnology and Bioengineering',
                    'Chemistry and Chemical Engineering',
                    'Civil and Environmental Engineering',
                    'Computational and Quantitative Biology',
                    'Computer and Communication Sciences',
                    'Digital Humanities',
                    'Electrical Engineering',
                    'Energy',
                    'Finance',
                    'Learning Sciences',
                    'Management of Technology',
                    'Materials Science and Engineering',
                    'Mathematics',
                    'Mechanics',
                    'Microsystems and Microelectronics',
                    'Molecular Life Sciences',
                    'Neuroscience',
                    'Photonics',
                    'Physics',
                    'Robotics, Control and Intelligent Systems'
                ]
            }
        },{
            key: 'minor',
            question: 'Which minor?',
            getOptions: (formData) => {
                if (formData.program === 'Master') {
                return [
                    'Architecture',
                    'Biomedical Technologies',
                    'Biotechnology',
                    'Chemistry and Chemical Engineering',
                    'Civil Engineering',
                    'Communication Systems',
                    'Computational Biology',
                    'Computational Science and Engineering',
                    'Computer science',
                    'Cyber Security',
                    'Data and Internet of Things',
                    'Data Science',
                    'Digital Humanities, Media and Society',
                    'Electrical and Electronic Engineering',
                    'Energy',
                    'Engineering for sustainability',
                    'Environmental Sciences and Engineering',
                    'Financial engineering',
                    'Imaging',
                    'Integrated Design, Architecture and Sustainability (IDEAS)',
                    'Life Sciences Engineering',
                    'Materials Science and Engineering',
                    'Mathematics',
                    'Mechanical Engineering',
                    'Microengineering',
                    'Neuro-X',
                    'Photonics',
                    'Physics',
                    'Physics of Living Systems',
                    'Quantum Science and Engineering',
                    'Spacial Technologies',
                    'Statistics',
                    'Systems Engineering',
                    'Technology management and entrepreneurship',
                    'Territories in Transformation and Climate (TTC)'
                ];
                }
                return []; // No options if not Master
            }
            }
    ]

    const handleAnswer = (value) => {
        const key = allQuestions[currentStep].key;
        setFormData(prev => ({ ...prev, [key]: value }));
        if (currentStep < allQuestions.length - 1) {
            setCurrentStep(prev => prev + 1);
        } else {
            handleSubmit();
        }
    };

    const handleSubmit = () => {
        setIsFinished(true);
    };

    const q = allQuestions[currentStep];

    // Determine options for current question, either from options or getOptions
    let options = q.options;
    if (!options && q.getOptions) {
        options = q.getOptions(formData);
    }
    if (!options) options = [];

    // If options is empty array, automatically skip to next step with empty string answer
    useEffect(() => {
        if (options.length === 0) {
            handleAnswer('');
        }
    }, [currentStep]); // run when currentStep changes

    return (
        <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh',width: '100vw'}}>
            {isFinished ? (
                <h2>Finished!</h2>
            ) : (
                <div style={{textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '20px'}}>
                    <h2>{q.question}</h2>
                    {(q.key === 'major' || q.key === 'minor') ? (
                        <div style={{display: 'flex', flexDirection: 'row', gap: '10px', justifyContent: 'center', alignItems: 'center'}}>
                            <select
                                value={formData[q.key]}
                                onChange={(e) => setFormData(prev => ({ ...prev, [q.key]: e.target.value }))}
                            >
                                <option value="" disabled>Select an option</option>
                                {options.map(opt => (
                                    <option key={opt} value={opt}>{opt}</option>
                                ))}
                            </select>
                            <button onClick={() => handleAnswer(formData[q.key])} disabled={!formData[q.key]}>Next</button>
                        </div>
                    ) : (
                        <div style={{display: 'flex', flexDirection: 'row', gap: '10px', justifyContent: 'center', alignItems: 'center'}}>
                            {options.map(opt => (
                                <button key={opt} onClick={() => handleAnswer(opt)}>
                                    {opt}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default Questionnaire;