import {readFileSync} from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';

const schema = JSON.parse(
  readFileSync(
    new URL('../../../packages/contracts/schemas/private_credential.schema.json', import.meta.url),
    'utf8',
  ),
);
const ajv = new Ajv2020({strict: true, allErrors: false});
ajv.addSchema(schema);

export function check(type, value) {
  const validator = ajv.getSchema(`${schema.$id}#/$defs/${type}`);
  if (!validator?.(value)) {
    throw new Error(`Invalid ${type}`);
  }
  return value;
}
