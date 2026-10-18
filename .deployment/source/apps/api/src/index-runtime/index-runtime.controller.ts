import { Body, Controller, Delete, Get, Param, Patch, Post, Query, Req, Res, UploadedFile, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import type { Response } from 'express';
import { ApiBearerAuth, ApiHeader, ApiTags } from '@nestjs/swagger';
import type { AppRequest,Principal } from '../common/types';
import { IndexRuntimeService } from './index-runtime.service';
import { DomainException } from '../common/http/domain.exception';
import { HttpStatus } from '@nestjs/common';

@ApiTags('Index Runtime')
@ApiBearerAuth()
@ApiHeader({name:'AppId',required:true,example:1})
@ApiHeader({name:'ServiceId',required:true,example:1})
@ApiHeader({name:'CorrelationId',required:true,example:'index-runtime-01'})
@ApiHeader({name:'UserId',required:true,schema:{type:'integer',format:'int64'}})
@ApiHeader({name:'Language',required:true,example:'fa'})
@Controller('api/v1/index-runtime')
export class IndexRuntimeController{
 constructor(private readonly service:IndexRuntimeService){}
 private principal(request:AppRequest):Principal{const actor=request.zohaContext?.actor;if(!actor)throw new DomainException('Common.Unauthorized',HttpStatus.UNAUTHORIZED);return actor;}
 @Post('files/upload') @UseInterceptors(FileInterceptor('file',{limits:{fileSize:10485760,files:1}}))
 upload(@Req() r:AppRequest,@Body() b:{contentType:string;fieldKey:string},@UploadedFile() file?:{originalname:string;mimetype:string;size:number;buffer:Buffer}){return this.service.uploadFieldFile(this.principal(r),b.contentType,b.fieldKey,file)}
 @Get('files/:fileId') async download(@Req() r:AppRequest,@Param('fileId') id:string,@Res() res:Response){const f=await this.service.downloadFieldFile(this.principal(r),id);res.setHeader('Content-Type','application/octet-stream');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Content-Disposition',`attachment; filename*=UTF-8''${encodeURIComponent(f.name)}`);res.send(f.buffer)}
 @Get('schema/:contentType') schema(@Param('contentType') t:string){return this.service.schema(t)}
 @Get('taxonomies/:code/options') options(@Req() r:AppRequest,@Param('code') c:string,@Query('q') q='',@Query('parent') p='',@Query('parentId') parentId='',@Query('parentScope') parentScope='',@Query('contentType') contentType=''){return this.service.options(this.principal(r),c,q,p,parentId,parentScope,contentType)}
 @Get('personal') personal(@Req() r:AppRequest,@Query('taxonomy') c?:string){return this.service.listPersonal(this.principal(r),c)}
 @Post('taxonomies/:code/personal') add(@Req() r:AppRequest,@Param('code') c:string,@Body() b:{title?:string,contentType?:string,parentSystemTermId?:number|string,parentUserTermId?:number|string}){return this.service.createPersonal(this.principal(r),c,b)}
 @Patch('personal/:id') edit(@Req() r:AppRequest,@Param('id') id:string,@Body() b:{title:string}){return this.service.updatePersonal(this.principal(r),Number(id),b.title)}
 @Delete('personal/:id') del(@Req() r:AppRequest,@Param('id') id:string){return this.service.deletePersonal(this.principal(r),Number(id))}
 @Get(':contentType/:contentId') load(@Req() r:AppRequest,@Param('contentType') t:string,@Param('contentId') id:string){return this.service.loadPayload(this.principal(r),t,id)}
 @Post(':contentType/:contentId') save(@Req() r:AppRequest,@Param('contentType') t:string,@Param('contentId') id:string,@Body() b:{payload:unknown}){return this.service.savePayload(this.principal(r),t,id,b.payload)}
}
