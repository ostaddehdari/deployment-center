import { Body, Controller, Delete, Get, Param, Patch, Post, Query, Req } from '@nestjs/common';
import { ApiBearerAuth, ApiHeader, ApiOperation, ApiTags } from '@nestjs/swagger';
import type { AppRequest } from '../common/types';
import { AdminRuntimeIndexService } from './admin-runtime-index.service';
import { CreateRuntimeTermDTO, ReorderRuntimeFieldsDTO, UpdateRuntimePostTypeFieldDTO, UpdateRuntimeTaxonomyDTO, UpdateRuntimeTermDTO } from './admin-runtime-index.dto';

@ApiTags('Admin Runtime Index Builder')
@ApiBearerAuth()
@ApiHeader({name:'AppId',required:true,example:1})
@ApiHeader({name:'ServiceId',required:true,example:1})
@ApiHeader({name:'CorrelationId',required:true,example:'admin-runtime-index-01'})
@ApiHeader({name:'UserId',required:true,schema:{type:'integer',format:'int64'}})
@ApiHeader({name:'Language',required:true,example:'fa'})
@Controller('api/admin/runtime-index/v1')
export class AdminRuntimeIndexController {
  constructor(private readonly runtime:AdminRuntimeIndexService){}
  private actor(request:AppRequest){return request.zohaContext?.actor??null;}

  @Get('overview') @ApiOperation({summary:'نمایه‌های واقعی Runtime برای یک نوع محتوا'})
  overview(@Req() request:AppRequest,@Query('contentType') contentType?:string){return this.runtime.overview(this.actor(request),contentType);}

  @Get('preview/schema/:contentType')
  previewSchema(@Req() request:AppRequest,@Param('contentType') contentType:string){return this.runtime.previewSchema(this.actor(request),contentType);}
  @Get('preview/taxonomies/:code/options')
  previewOptions(@Req() request:AppRequest,@Param('code') code:string,@Query('q') q='',@Query('parent') parent='',@Query('parentId') parentId='',@Query('parentScope') parentScope='',@Query('contentType') contentType=''){return this.runtime.previewOptions(this.actor(request),code,q,parent,parentId,parentScope,contentType);}

  @Post('post-types/:contentType/fields/:taxonomyCode')
  assignField(@Req() request:AppRequest,@Param('contentType') contentType:string,@Param('taxonomyCode') taxonomyCode:string){return this.runtime.assignField(this.actor(request),contentType,taxonomyCode);}
  @Patch('post-types/:contentType/fields/:taxonomyCode')
  updateField(@Req() request:AppRequest,@Param('contentType') contentType:string,@Param('taxonomyCode') taxonomyCode:string,@Body() body:UpdateRuntimePostTypeFieldDTO){return this.runtime.updateField(this.actor(request),contentType,taxonomyCode,body);}
  @Delete('post-types/:contentType/fields/:taxonomyCode')
  removeField(@Req() request:AppRequest,@Param('contentType') contentType:string,@Param('taxonomyCode') taxonomyCode:string){return this.runtime.removeField(this.actor(request),contentType,taxonomyCode);}
  @Post('post-types/:contentType/reorder')
  reorder(@Req() request:AppRequest,@Param('contentType') contentType:string,@Body() body:ReorderRuntimeFieldsDTO){return this.runtime.reorder(this.actor(request),contentType,body);}

  @Patch('taxonomies/:code')
  updateTaxonomy(@Req() request:AppRequest,@Param('code') code:string,@Body() body:UpdateRuntimeTaxonomyDTO){return this.runtime.updateTaxonomy(this.actor(request),code,body);}
  @Get('taxonomies/:code/terms')
  terms(@Req() request:AppRequest,@Param('code') code:string,@Query('q') q='',@Query('page') page='1',@Query('pageSize') pageSize='50',@Query('includeInactive') includeInactive='false'){return this.runtime.terms(this.actor(request),code,q,page,pageSize,includeInactive);}
  @Post('taxonomies/:code/terms')
  createTerm(@Req() request:AppRequest,@Param('code') code:string,@Body() body:CreateRuntimeTermDTO){return this.runtime.createTerm(this.actor(request),code,body);}
  @Patch('taxonomies/:code/terms/:id')
  updateTerm(@Req() request:AppRequest,@Param('code') code:string,@Param('id') id:string,@Body() body:UpdateRuntimeTermDTO){return this.runtime.updateTerm(this.actor(request),code,id,body);}
  @Delete('taxonomies/:code/terms/:id')
  deleteTerm(@Req() request:AppRequest,@Param('code') code:string,@Param('id') id:string){return this.runtime.deleteTerm(this.actor(request),code,id);}
}
