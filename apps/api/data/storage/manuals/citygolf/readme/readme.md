# 📘 Manual RAG Service

이 서비스는 매뉴얼을 업로드하고 RAG 기반으로 학습하여, 사용자의 질문에 대해 정확한 정보를 제공합니다.

## 사용 방법
1. 매뉴얼 파일을 업로드합니다.
2. 시스템이 문서를 자동으로 분석 및 임베딩합니다.
3. 주요 내용이 벡터 DB에 저장됩니다.
4. 학습 완료 후 질문 입력이 가능합니다.
5. 질문을 입력하면 관련 문서 기반으로 답변을 생성합니다.
6. 답변은 업로드한 문서 범위 내에서만 제공됩니다.
7. 근거 기반 응답으로 홀로시네이션을 최소화합니다.
8. 필요 시 Reference(출처)도 함께 확인할 수 있습니다.
-----------------------------------------------
Este servicio permite subir manuales, procesarlos con RAG y responder preguntas con información precisa basada en los documentos.

## Uso
1. Suba el archivo del manual.
2. El sistema analiza y genera embeddings automáticamente.
3. La información se almacena en una base de datos vectorial.
4. Una vez finalizado el proceso, puede realizar preguntas.
5. Ingrese su pregunta en el sistema.
6. La respuesta se genera basada únicamente en el contenido del manual.
7. Se minimiza la alucinación mediante respuestas basadas en evidencia.
8. Puede verificar también las referencias (fuentes) relacionadas.