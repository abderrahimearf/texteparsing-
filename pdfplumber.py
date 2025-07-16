import streamlit as st
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import base64
from datetime import datetime
import warnings


warnings.filterwarnings("ignore")

LIBRARIES_STATUS = {
    "docling": False,
    "pymupdf": False,
    "pdfplumber": False
}


try:
    import fitz  
    LIBRARIES_STATUS["pymupdf"] = True
except:
    pass

try:
    import pdfplumber
    LIBRARIES_STATUS["pdfplumber"] = True
except:
    pass

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    LIBRARIES_STATUS["docling"] = True
except:
    pass

class PDFAnalyzer:
    """Analyseur PDF universel qui utilise la meilleure bibliothèque disponible"""
    
    def __init__(self):
        self.method = None
        
        # Déterminer quelle méthode utiliser
        if LIBRARIES_STATUS["pymupdf"]:
            self.method = "pymupdf"
        elif LIBRARIES_STATUS["pdfplumber"]:
            self.method = "pdfplumber"
        elif LIBRARIES_STATUS["docling"]:
            self.method = "docling"
            try:
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = False
                pipeline_options.do_table_structure = True
                
                self.converter = DocumentConverter(
                    allowed_formats=[InputFormat.PDF],
                    pipeline_options=pipeline_options
                )
            except:
                self.method = None
    
    def analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Analyse un PDF avec la méthode disponible"""
        if self.method == "pymupdf":
            return self._analyze_with_pymupdf(pdf_path)
        elif self.method == "pdfplumber":
            return self._analyze_with_pdfplumber(pdf_path)
        elif self.method == "docling":
            return self._analyze_with_docling(pdf_path)
        else:
            raise Exception("Aucune bibliothèque PDF disponible pour l'analyse")
    
    def _analyze_with_pymupdf(self, pdf_path: str) -> Dict[str, Any]:
        """Analyse avec PyMuPDF"""
        import fitz
        
        doc = fitz.open(pdf_path)
       
        title = doc.metadata.get('title', '')
        if not title:
            first_page = doc[0]
            first_text = first_page.get_text()[:100]
            title = first_text.split('\n')[0] if first_text else "Document sans titre"
        
        structure = {
            "title": title,
            "metadata": {
                "num_pages": doc.page_count,
                "author": doc.metadata.get('author', ''),
                "subject": doc.metadata.get('subject', ''),
                "extraction_date": datetime.now().isoformat(),
                "extraction_method": "PyMuPDF"
            },
            "sections": []
        }
        
        current_section = None
        current_subsection = None
        
        for page_num, page in enumerate(doc):
       
            blocks = page.get_text("dict")
            
     
            for block in blocks["blocks"]:
                if block["type"] == 0: 
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if not text:
                                continue
                            
                            font_size = span["size"]
                            font_flags = span["flags"]
                            
                           
                            is_bold = font_flags & 2**4
                            is_italic = font_flags & 2**1
                            
                         
                            if font_size > 16 or (is_bold and font_size > 12):
                                current_section = {
                                    "title": text,
                                    "subsections": []
                                }
                                structure["sections"].append(current_section)
                                current_subsection = None
                            
                    
                            elif (font_size > 14 or (is_bold and font_size > 11)) and current_section:
                                current_subsection = {
                                    "title": text,
                                    "content": []
                                }
                                current_section["subsections"].append(current_subsection)
                            
                     
                            else:
                                self._add_content(text, structure, current_section, current_subsection)
                
                elif block["type"] == 1:  
                    image_info = {
                        "image": {
                            "description": f"Image détectée (dimensions: {block.get('width', 0)}x{block.get('height', 0)})",
                            "position": f"page {page_num + 1}"
                        }
                    }
                    self._add_content(image_info, structure, current_section, current_subsection)
            
           
            tables = page.find_tables()
            for table_num, table in enumerate(tables):
                table_data = {
                    "type": "table",
                    "caption": f"Tableau {table_num + 1} - Page {page_num + 1}",
                    "headers": [],
                    "rows": []
                }
                
               
                for row in table.extract():
                    if not table_data["headers"]:
                        table_data["headers"] = [str(cell) if cell else "" for cell in row]
                    else:
                        table_data["rows"].append([str(cell) if cell else "" for cell in row])
                
                self._add_content(table_data, structure, current_section, current_subsection)
        
        doc.close()
        return structure
    
    def _analyze_with_pdfplumber(self, pdf_path: str) -> Dict[str, Any]:
        """Analyse avec pdfplumber"""
        import pdfplumber
        
        structure = {
            "title": "Document PDF",
            "metadata": {
                "num_pages": 0,
                "extraction_date": datetime.now().isoformat(),
                "extraction_method": "pdfplumber"
            },
            "sections": []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
          
            structure["metadata"]["num_pages"] = len(pdf.pages)
            if pdf.metadata:
                structure["title"] = pdf.metadata.get('Title', 'Document PDF')
                structure["metadata"]["author"] = pdf.metadata.get('Author', '')
                structure["metadata"]["subject"] = pdf.metadata.get('Subject', '')
            
         
            for page_num, page in enumerate(pdf.pages):
                
                section = {
                    "title": f"Page {page_num + 1}",
                    "subsections": [{
                        "title": "Contenu",
                        "content": []
                    }]
                }
                structure["sections"].append(section)
            
                text = page.extract_text()
                if text:
                  
                    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                    for para in paragraphs:
                        section["subsections"][0]["content"].append(para)
                
            
                tables = page.extract_tables()
                for i, table in enumerate(tables):
                    if table and len(table) > 0:
                        table_data = {
                            "type": "table",
                            "caption": f"Tableau {i+1}",
                            "headers": table[0] if table else [],
                            "rows": table[1:] if len(table) > 1 else []
                        }
                        section["subsections"][0]["content"].append(table_data)
                
            
                if hasattr(page, 'images'):
                    for img_num, img in enumerate(page.images or []):
                        image_info = {
                            "image": {
                                "description": f"Image {img_num + 1}",
                                "position": f"page {page_num + 1}"
                            }
                        }
                        section["subsections"][0]["content"].append(image_info)
        
        return structure
    
    def _analyze_with_docling(self, pdf_path: str) -> Dict[str, Any]:
        """Analyse avec Docling"""
        try:
            result = self.converter.convert(pdf_path)
            doc = result.document
            
            structure = {
                "title": self._get_doc_title(doc),
                "metadata": {
                    "num_pages": len(doc.pages) if hasattr(doc, 'pages') else 0,
                    "extraction_date": datetime.now().isoformat(),
                    "extraction_method": "Docling"
                },
                "sections": []
            }
            
        
            current_section = None
            current_subsection = None
            
            for item in doc.iterate_items():
                item_type = item.label if hasattr(item, 'label') else 'unknown'
                
                if item_type in ['section_header', 'header', 'title']:
                    if self._is_main_title(item):
                        current_section = {
                            "title": item.text,
                            "subsections": []
                        }
                        structure["sections"].append(current_section)
                        current_subsection = None
                    else:
                        if current_section is None:
                            current_section = {
                                "title": "Section principale",
                                "subsections": []
                            }
                            structure["sections"].append(current_section)
                        
                        current_subsection = {
                            "title": item.text,
                            "content": []
                        }
                        current_section["subsections"].append(current_subsection)
                
                elif item_type in ['paragraph', 'text']:
                    self._add_content(item.text, structure, current_section, current_subsection)
                
                elif item_type == 'table':
                    table_content = {
                        "type": "table",
                        "caption": getattr(item, 'caption', 'Tableau'),
                        "headers": [],
                        "rows": []
                    }
                    self._add_content(table_content, structure, current_section, current_subsection)
                
                elif item_type in ['figure', 'image']:
                    image_info = {
                        "image": {
                            "description": getattr(item, 'caption', 'Image'),
                            "position": f"page {getattr(item, 'page_number', 'inconnue')}"
                        }
                    }
                    self._add_content(image_info, structure, current_section, current_subsection)
            
            return structure
            
        except Exception as e:
            raise Exception(f"Erreur Docling: {str(e)}")
    
    def _add_content(self, content: Any, structure: Dict, section: Optional[Dict], subsection: Optional[Dict]):
        """Ajoute du contenu à la structure"""
        if subsection is not None:
            subsection["content"].append(content)
        elif section is not None:
            if not section["subsections"]:
                section["subsections"].append({
                    "title": "Contenu",
                    "content": []
                })
            section["subsections"][-1]["content"].append(content)
        else:
            if not structure["sections"]:
                structure["sections"].append({
                    "title": "Contenu principal",
                    "subsections": [{
                        "title": "Introduction",
                        "content": []
                    }]
                })
            structure["sections"][-1]["subsections"][-1]["content"].append(content)
    
    def _get_doc_title(self, doc) -> str:
        """Extrait le titre d'un document Docling"""
        for item in doc.iterate_items():
            if hasattr(item, 'label') and item.label in ['title', 'document_title']:
                return item.text
        return "Document sans titre"
    
    def _is_main_title(self, item) -> bool:
        """Vérifie si c'est un titre principal"""
        return hasattr(item, 'level') and item.level == 1

def display_structure_preview(structure: Dict[str, Any]):
    """Affiche un aperçu structuré du contenu extrait"""
    st.header(" Aperçu du contenu extrait")
    

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"**{structure['title']}**")
    with col2:
        method = structure['metadata'].get('extraction_method', 'Inconnue')
        st.caption(f"Méthode: {method}")
    
  
    with st.expander(" Métadonnées"):
        st.json(structure['metadata'])
    

    for i, section in enumerate(structure['sections']):
        with st.expander(f"📂 {section['title']}", expanded=(i == 0)):
            for j, subsection in enumerate(section['subsections']):
                st.markdown(f"### {subsection['title']}")
                
                for content in subsection['content']:
                    if isinstance(content, str):
                        st.write(content)
                    elif isinstance(content, dict):
                        if content.get('type') == 'list':
                            st.markdown("**Liste:**")
                            for item in content['items']:
                                st.markdown(f"- {item}")
                        elif content.get('type') == 'table':
                            st.markdown(f"**{content.get('caption', 'Tableau')}**")
                            if content['headers'] and content['rows']:
                                import pandas as pd
                                try:
                                    df = pd.DataFrame(content['rows'], columns=content['headers'])
                                    st.dataframe(df, use_container_width=True)
                                except:
                                    st.write("Données du tableau:", content)
                        elif 'image' in content:
                            img = content['image']
                            st.info(f"🖼️ **Image:** {img['description']} ({img['position']})")

def download_json(data: Dict[str, Any], filename: str = "document_structure.json"):
   
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    
    st.download_button(
        label=" Télécharger le fichier JSON",
        data=json_str,
        file_name=filename,
        mime="application/json"
    )

def main():
    st.set_page_config(
        page_title="Analyseur PDF ",
      
        layout="wide"
    )
    
    st.title(" Extraction de structure")
    st.markdown("""
    Cette application analyse la structure de vos documents PDF et génère un fichier JSON structuré.
    """)
    
   
   
 
    if not any(LIBRARIES_STATUS.values()):
        st.error("Impossible de continuer sans bibliothèque PDF. Veuillez en installer une.")
        return

    uploaded_file = st.file_uploader(
        "Choisissez un fichier PDF",
        type=['pdf'],
        help="Sélectionnez un fichier PDF à analyser"
    )
    
    if uploaded_file is not None:
       
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fichier", uploaded_file.name)
        with col2:
            st.metric("Taille", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Type", "PDF")
        
 
        if st.button(" Analyser le document", type="primary", use_container_width=True):
            with st.spinner("Analyse en cours... Cela peut prendre quelques instants selon la taille du document."):
                try:
                   
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    
                    analyzer = PDFAnalyzer()
                    structure = analyzer.analyze_pdf(tmp_path)
                    
                    st.session_state['analysis_result'] = structure
                    st.session_state['filename'] = uploaded_file.name
                    
                 
                    Path(tmp_path).unlink()
                    
                    st.success("✅ Analyse terminée avec succès!")
                    
                    
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'analyse: {str(e)}")
                    st.info("Vérifiez que le fichier PDF n'est pas corrompu ou protégé.")
    

    if 'analysis_result' in st.session_state:
        st.divider()
        
    
        display_structure_preview(st.session_state['analysis_result'])
        
        st.divider()
        
      
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            json_filename = f"{Path(st.session_state['filename']).stem}_structure.json"
            download_json(st.session_state['analysis_result'], json_filename)
        
        with col2:
            if st.button(" Voir le JSON complet", use_container_width=True):
                st.json(st.session_state['analysis_result'])
        
        with col3:
            if st.button(" Nouvelle analyse", use_container_width=True):
                del st.session_state['analysis_result']
                del st.session_state['filename']
                st.rerun()

if __name__ == "__main__":
    main()
