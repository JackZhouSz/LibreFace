import os
from PIL import Image

import torch
import torch.nn as nn
from torchvision import transforms

from libreface.AU_Detection.models.resnet18 import ResNet18


class image_test(object):
	def __init__(self, img_size=256, crop_size=224):
		self.img_size = img_size
		self.crop_size = crop_size

	def __call__(self, img):
		transform = transforms.Compose([
			transforms.Resize(self.img_size),
			transforms.CenterCrop(self.crop_size),
			transforms.ToTensor(),
			transforms.Normalize(mean=[0.485, 0.456, 0.406],
								 std=[0.229, 0.224, 0.225])
		])
		img = transform(img)

		return img


class solver_in_domain_image(nn.Module):
	def __init__(self, config):
		super(solver_in_domain_image, self).__init__()
		self.config = config

		# Setup number of labels
		self.config.num_labels = 12
		self.num_labels = self.config.num_labels

		self.image_transform = image_test(img_size=config.image_size, crop_size=config.crop_size)

		self.device = config.device

		# Initiate the networks
		if config.model_name == "resnet":
			self.model = ResNet18(config).to(self.device)
		else:
			raise NotImplementedError

   
		if self.config.half_precision:
			print("Use Half Precision.")
		
		# Setup AU index
		if self.config.data == 'BP4D':
			self.aus = [1,2,4,6,7,10,12,14,15,17,23,24]

	def pil_loader(self, path):
		with open(path, 'rb') as f:
			with Image.open(f) as img:
				return img.convert('RGB')

	def transform_image_inference(self, aligned_image_path):

		image = self.pil_loader(aligned_image_path)
		image = self.image_transform(image)

		return image

	def image_inference(self, transformed_image):
		with torch.no_grad():
			self.eval()
			input_image = torch.unsqueeze(transformed_image, 0).to(self.device)
			if self.config.half_precision:
				input_image = input_image.half()
				self.model = self.model.half()
			labels_pred = self.model(input_image)
			if self.config.half_precision:
				labels_pred = labels_pred.float()
			labels_pred = (labels_pred >= 0.5).int()
			return labels_pred


	def load_best_ckpt(self):
		ckpt_name = os.path.join(self.config.ckpt_path, self.config.data, self.config.fold, self.config.model_name+'.pt')
		checkpoints = torch.load(ckpt_name)['model']
		self.model.load_state_dict(checkpoints, strict=True)


	def run(self, aligned_image_path):

		patience = self.config.patience
		if "cuda" in self.device:
			torch.backends.cudnn.benchmark = True

		# Test model
		self.load_best_ckpt()
		transformed_image = self.transform_image_inference(aligned_image_path)
		pred_labels = self.image_inference(transformed_image)
		pred_labels = pred_labels.squeeze().tolist()
		return dict(zip(self.aus, pred_labels))
