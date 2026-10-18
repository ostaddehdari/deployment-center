import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsArray, IsBoolean, IsIn, IsInt, IsObject, IsOptional, IsString, Max, MaxLength, Min, Matches } from 'class-validator';

export const RUNTIME_INDEX_FIELD_TYPES=['taxonomy','choice','text','textarea'] as const;

export class UpdateRuntimeTaxonomyDTO {
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(240) Title?:string;
  @ApiPropertyOptional({enum:RUNTIME_INDEX_FIELD_TYPES}) @IsOptional() @IsIn(RUNTIME_INDEX_FIELD_TYPES) FieldType?:string;
  @ApiPropertyOptional() @IsOptional() @IsBoolean() IsMulti?:boolean;
  @ApiPropertyOptional() @IsOptional() @IsBoolean() AllowsPersonal?:boolean;
  @ApiPropertyOptional() @IsOptional() @IsBoolean() IsActive?:boolean;
  @ApiPropertyOptional({type:'object',additionalProperties:true}) @IsOptional() @IsObject() Metadata?:Record<string,unknown>;
}

export class UpdateRuntimePostTypeFieldDTO {
  @ApiPropertyOptional() @IsOptional() @IsBoolean() IsRequired?:boolean;
  @ApiPropertyOptional({type:'object',additionalProperties:true}) @IsOptional() @IsObject() Settings?:Record<string,unknown>;
}

export class ReorderRuntimeFieldsDTO {
  @ApiProperty({type:[String]}) @IsArray() @IsString({each:true}) TaxonomyCodes!:string[];
}

export class CreateRuntimeTermDTO {
  @ApiProperty() @IsString() @MaxLength(240) Title!:string;
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(240) ParentHint?:string;
  @ApiPropertyOptional() @IsOptional() @IsString() @Matches(/^[0-9]+$/) ParentId?:string;
  @ApiPropertyOptional() @IsOptional() @IsInt() @Min(-100000) @Max(100000) SortOrder?:number;
  @ApiPropertyOptional({type:'object',additionalProperties:true}) @IsOptional() @IsObject() Metadata?:Record<string,unknown>;
}

export class UpdateRuntimeTermDTO {
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(240) Title?:string;
  @ApiPropertyOptional() @IsOptional() @IsString() @MaxLength(240) ParentHint?:string;
  @ApiPropertyOptional() @IsOptional() @IsString() @Matches(/^[0-9]+$/) ParentId?:string;
  @ApiPropertyOptional() @IsOptional() @IsInt() @Min(-100000) @Max(100000) SortOrder?:number;
  @ApiPropertyOptional() @IsOptional() @IsBoolean() IsActive?:boolean;
  @ApiPropertyOptional({type:'object',additionalProperties:true}) @IsOptional() @IsObject() Metadata?:Record<string,unknown>;
}
