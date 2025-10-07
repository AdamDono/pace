COURSE_TEMPLATES = {
    'beginner': {
        'title': 'Introduction to [Subject]',
        'description': 'A comprehensive beginner-friendly course designed for complete newcomers. This course covers all the fundamental concepts and provides hands-on practice to build a strong foundation in [subject].',
        'learning_objectives': '''• Understand the basic concepts and terminology
• Learn fundamental principles and techniques
• Practice with real-world examples
• Build confidence through hands-on exercises
• Create your first [subject] project''',
        'prerequisites': '''• No prior experience required
• Basic computer skills
• Willingness to learn and practice''',
        'tags': 'beginner, fundamentals, introduction, basics',
        'estimated_duration': 20,
        'difficulty_level': 'beginner'
    },
    'intermediate': {
        'title': 'Advanced [Subject] Techniques',
        'description': 'Take your skills to the next level with intermediate to advanced techniques. This course assumes basic knowledge and dives deep into professional practices, best patterns, and real-world applications.',
        'learning_objectives': '''• Master advanced concepts and techniques
• Learn industry best practices and patterns
• Build complex, real-world projects
• Optimize performance and efficiency
• Collaborate on professional-grade applications''',
        'prerequisites': '''• Basic understanding of [subject] fundamentals
• Experience with simple projects
• Familiarity with development environment''',
        'tags': 'intermediate, advanced, professional, best-practices',
        'estimated_duration': 40,
        'difficulty_level': 'intermediate'
    },
    'project': {
        'title': 'Build a Complete [Subject] Project',
        'description': 'Learn by doing in this project-based course. Starting from scratch, you\'ll build a complete, production-ready [subject] application while learning modern development practices and industry standards.',
        'learning_objectives': '''• Plan and architect a complete application
• Implement all major features and functionality
• Apply modern development practices
• Deploy and maintain a production application
• Collaborate with other developers''',
        'prerequisites': '''• Solid foundation in [subject] basics
• Experience with version control
• Understanding of web development concepts''',
        'tags': 'project, full-stack, production, real-world',
        'estimated_duration': 60,
        'difficulty_level': 'intermediate'
    },
    'specialized': {
        'title': 'Mastering [Subject]: [Specialty Area]',
        'description': 'Dive deep into a specialized area of [subject] with this advanced course. Perfect for developers looking to become experts in specific domains and cutting-edge technologies.',
        'learning_objectives': '''• Gain expertise in specialized [subject] domains
• Master advanced frameworks and libraries
• Understand complex architectural patterns
• Contribute to open-source projects
• Lead development teams and projects''',
        'prerequisites': '''• Strong foundation in [subject]
• Experience with multiple projects
• Understanding of advanced programming concepts''',
        'tags': 'advanced, specialized, expert, leadership',
        'estimated_duration': 80,
        'difficulty_level': 'advanced'
    }
}

def get_course_template(template_key, subject='Programming'):
    """Get a course template with subject filled in"""
    if template_key not in COURSE_TEMPLATES:
        return None

    template = COURSE_TEMPLATES[template_key].copy()

    # Replace [subject] placeholders
    template['title'] = template['title'].replace('[Subject]', subject).replace('[subject]', subject.lower())
    template['description'] = template['description'].replace('[subject]', subject.lower()).replace('[Subject]', subject)
    template['learning_objectives'] = template['learning_objectives'].replace('[subject]', subject.lower())
    template['prerequisites'] = template['prerequisites'].replace('[subject]', subject.lower())

    return template
