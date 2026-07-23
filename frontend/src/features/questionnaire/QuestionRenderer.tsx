import type { QuestionComponentProps } from './questions/types'
import { BooleanQuestion } from './questions/BooleanQuestion'
import { CurrencyQuestion } from './questions/CurrencyQuestion'
import { DateQuestion } from './questions/DateQuestion'
import { InformationQuestion } from './questions/InformationQuestion'
import { MultiChoiceQuestion } from './questions/MultiChoiceQuestion'
import { NumberQuestion } from './questions/NumberQuestion'
import { SingleChoiceQuestion } from './questions/SingleChoiceQuestion'
import { TextQuestion } from './questions/TextQuestion'
import { DocumentUploadQuestion } from '../documents/DocumentUploadQuestion'
import { ReviewCardQuestion } from '../review/ReviewCardQuestion'

/**
 * The only place question_type -> component dispatch happens. This is
 * presentation dispatch only (which input widget to draw) — it does not
 * decide which question comes next, evaluate any rule, or compute
 * progress; that's exclusively the backend's job (see QuestionnaireRunnerPage).
 */
export function QuestionRenderer(props: QuestionComponentProps) {
  switch (props.question.question_type) {
    case 'BOOLEAN':
      return <BooleanQuestion {...props} />
    case 'SINGLE_CHOICE':
      return <SingleChoiceQuestion {...props} />
    case 'MULTI_CHOICE':
      return <MultiChoiceQuestion {...props} />
    case 'TEXT':
      return <TextQuestion {...props} />
    case 'NUMBER':
      return <NumberQuestion {...props} />
    case 'CURRENCY':
      return <CurrencyQuestion {...props} />
    case 'DATE':
      return <DateQuestion {...props} />
    case 'INFORMATION':
      return <InformationQuestion {...props} />
    case 'DOCUMENT_UPLOAD':
      return <DocumentUploadQuestion {...props} />
    case 'REVIEW_CARD':
      return <ReviewCardQuestion {...props} />
  }
}
