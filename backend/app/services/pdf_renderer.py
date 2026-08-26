from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import datetime
from ..models.paper import Paper

class PDFRenderer:
    """
    Handles PDF generation from structured paper content
    """
    def __init__(self, content: Dict[str, Any]):
        self.content = content

    def generate(self) -> bytes:
        """
        Generate PDF bytes from the paper content
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Add institution header
        if 'institution' in self.content:
            heading = Paragraph(f"<b>{self.content['institution']}</b>", styles['Heading1'])
            story.append(heading)
            story.append(Spacer(1, 24))

        # Add department
        if 'department' in self.content:
            heading = Paragraph(f"<b>{self.content['department']}</b>", styles['Heading2'])
            story.append(heading)
            story.append(Spacer(1, 12))

        # Add examination details
        if 'examination' in self.content:
            exam_para = Paragraph(
                f"{self.content['examination']['name']} - {self.content['examination']['year']}",
                styles['Normal']
            )
            exam_para.alignment = 1  # Centered
            story.append(exam_para)
            story.append(Spacer(1, 12))

        # Add subject details
        if 'subject' in self.content:
            subject_para = Paragraph(
                f"{self.content['subject']['name']} (Subject Code: {self.content['subject']['code']}",
                styles['Heading3']
            )
            story.append(subject_para)
            
            duration_para = Paragraph(
                f"Duration: {self.content['subject']['duration']} minutes",
                styles['Normal']
            )
            duration_para.alignment = 1  # Centered
            story.append(duration_para)
            story.append(Spacer(1, 12))

        # Add instructions
        if 'instructions' in self.content:
            instructions = Paragraph("INSTRUCTIONS", styles['Heading4'])
            story.append(instructions)
            for instruction in self.content['instructions']:
                p = Paragraph(instruction, styles['BodyText'])
                p.leftIndent = 36  # 0.5 inch indent
                story.append(p)
            story.append(Spacer(1, 12))

        # Add sections and questions
        if 'sections' in self.content:
            for section in self.content['sections']:
                section_header = Paragraph(
                    f"{section['title']} (Total Marks: {section['total_marks']}",
                    styles['Heading5']
                )
                story.append(section_header)
                
                for question in section['questions']:
                    question_para = Paragraph(
                        f"{question['number}]. {question['text']} [Marks: {question['marks']}",
                        styles['BodyText']
                    )
                    question_para.leftIndent = 72  # 1 inch indent
                    story.append(question_para)
                    
                    if 'choices' in question:
                        for choice in question['choices']:
                            choice_para = Paragraph(f"- {choice}", styles['BodyText'])
                            choice_para.leftIndent = 108  # 1.5 inch indent
                            story.append(choice_para)

        doc.build(story)
        return buffer.getvalue()

    def render(self, content: str) -> bytes:
        """
        Render dynamic content to PDF
        """
        packet = BytesIO()
        can = canvas.Canvas(packet)
        can.drawString(100, 750, content)
        can.save()
        return packet.getvalue()